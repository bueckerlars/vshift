import json
from pathlib import Path

import pytest

from vshift.domain.transcoding_profile import (
    AudioSelectionMode,
    FrameRateType,
    QualityMode,
    SubtitleSelectionMode,
    VshiftProfile,
)
from vshift.exception import VShiftException
from vshift.infrastructure.handbrake.importer import HandBrakeImporter

HAND_BRAKE_LEAF = """
{
  "PresetName": "Fast 1080p30",
  "PresetDescription": "Test preset",
  "FileFormat": "mp4",
  "Folder": false,
  "VideoEncoder": "x264",
  "VideoQualityType": 2,
  "VideoQualitySlider": 22.0,
  "VideoFramerate": "30",
  "VideoFramerateMode": "pfr",
  "VideoPreset": "fast",
  "VideoProfile": "main",
  "VideoLevel": "4.0",
  "VideoMultiPass": true,
  "VideoTurboMultiPass": false,
  "PictureWidth": 1920,
  "PictureHeight": 1080,
  "AudioList": [
    {
      "AudioBitrate": 160,
      "AudioEncoder": "aac",
      "AudioMixdown": "stereo",
      "AudioSamplerate": "auto"
    }
  ],
  "AudioTrackSelectionBehavior": "first",
  "AudioLanguageList": ["eng"],
  "AudioCopyMask": ["copy:aac"],
  "SubtitleTrackSelectionBehavior": "foreign",
  "SubtitleLanguageList": ["eng"],
  "SubtitleTrackNamePassthru": true,
  "SubtitleBurnBehavior": "foreign",
  "ChapterMarkers": true,
  "Optimize": true,
  "ChildrenArray": []
}
"""

IMPORTER = HandBrakeImporter()


def test_parse_handbrake_preset_maps_to_vshift() -> None:
    profile = IMPORTER.parse_preset(json.loads(HAND_BRAKE_LEAF))

    assert profile.name == "Fast 1080p30"
    assert profile.description == "Test preset"
    assert profile.format == "mp4"
    assert profile.video.codec == "h264"
    assert profile.video.quality_mode == QualityMode.CONSTANT
    assert profile.video.quality == 22.0
    assert profile.video.width == 1920
    assert profile.video.height == 1080
    assert profile.video.frame_rate_type == FrameRateType.CUSTOM
    assert profile.video.frame_rate == 30.0
    assert profile.video.multi_pass is True
    assert profile.optimize is True
    assert len(profile.audio_tracks) == 1
    assert profile.audio_tracks[0].codec == "aac"
    assert profile.audio_tracks[0].bit_rate == 160
    assert profile.audio_selection_mode == AudioSelectionMode.FIRST
    assert profile.audio_language_list == ["eng"]
    assert profile.audio_passthrough is True
    assert profile.subtitle_selection_mode == SubtitleSelectionMode.FOREIGN
    assert profile.subtitle_language_list == ["eng"]
    assert profile.subtitle_passthrough is True
    assert len(profile.subtitle_tracks) == 1
    assert profile.subtitle_tracks[0].copy_track is True


def test_legacy_handbrake_fields() -> None:
    data = json.loads(HAND_BRAKE_LEAF)
    data["VideoTwoPass"] = True
    data["VideoTurboTwoPass"] = True
    data["Mp4HttpOptimize"] = True
    del data["VideoMultiPass"]
    del data["VideoTurboMultiPass"]
    del data["Optimize"]

    profile = IMPORTER.parse_preset(data)
    assert profile.video.multi_pass is True
    assert profile.video.turbo_multi_pass is True
    assert profile.optimize is True


def test_parse_handbrake_presets_from_json_file_wrapper() -> None:
    leaf = json.loads(HAND_BRAKE_LEAF)
    document = {
        "VersionMajor": "11",
        "VersionMinor": 0,
        "VersionMicro": 0,
        "PresetList": [leaf],
    }
    profiles = IMPORTER.parse_presets_from_json(json.dumps(document))
    assert len(profiles) == 1
    assert profiles[0].name == "Fast 1080p30"


def test_parse_handbrake_presets_from_category_tree() -> None:
    leaf = json.loads(HAND_BRAKE_LEAF)
    leaf["PresetName"] = "Leaf Preset"
    document = [
        {
            "PresetName": "Category",
            "Folder": True,
            "ChildrenArray": [leaf],
        }
    ]
    profiles = IMPORTER.parse_presets_from_json(json.dumps(document))
    assert len(profiles) == 1
    assert any(profile.name == "Leaf Preset" for profile in profiles)


def test_vshift_profile_serializes_native_json() -> None:
    profile = IMPORTER.parse_preset(json.loads(HAND_BRAKE_LEAF))
    dumped = json.loads(profile.model_dump_json())

    assert dumped["name"] == "Fast 1080p30"
    assert dumped["video"]["codec"] == "h264"
    assert "PresetName" not in dumped


def test_parse_handbrake_audio_copy_encoder() -> None:
    data = json.loads(HAND_BRAKE_LEAF)
    data["AudioList"] = [
        {
            "AudioBitrate": 160,
            "AudioEncoder": "copy",
            "AudioMixdown": "stereo",
            "AudioSamplerate": "auto",
        }
    ]

    profile = IMPORTER.parse_preset(data)
    assert profile.audio_tracks[0].copy_track is True
    assert profile.audio_tracks[0].codec == "copy"


def test_parse_handbrake_4k_hdr_preset_from_fixture() -> None:
    fixture = Path(__file__).parent / "fixtures" / "handbrake" / "hq_4k_hdr_10bit.json"
    profiles = IMPORTER.parse_presets_from_file(fixture)
    profile = profiles[0]

    assert profile.format == "mkv"
    assert profile.video.codec == "h265"
    assert profile.video.bit_depth == 10
    assert profile.video.width == 3840
    assert profile.video.height == 2160
    assert profile.video.encoder_profile == "main10"
    assert profile.video.encoder_preset == "slower"
    assert profile.video.quality == 22.0
    assert profile.audio_tracks[0].copy_track is True


def test_average_bitrate_quality_mode() -> None:
    data = json.loads(HAND_BRAKE_LEAF)
    data["VideoQualityType"] = 1
    data["VideoAvgBitrate"] = 2500

    profile = IMPORTER.parse_preset(data)
    assert profile.video.quality_mode == QualityMode.AVERAGE_BITRATE
    assert profile.video.average_bitrate == 2500


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("quality", -1.0),
        ("average_bitrate", 0),
    ],
)
def test_vshift_profile_validation(field: str, value: float | int) -> None:
    profile = IMPORTER.parse_preset(json.loads(HAND_BRAKE_LEAF))
    video_data = profile.video.model_dump()
    if field == "quality":
        video_data["quality_mode"] = QualityMode.CONSTANT
        video_data[field] = value
    else:
        video_data["quality_mode"] = QualityMode.AVERAGE_BITRATE
        video_data[field] = value
    profile_data = profile.model_dump()
    profile_data["video"] = video_data
    with pytest.raises(VShiftException):
        VshiftProfile.model_validate(profile_data)

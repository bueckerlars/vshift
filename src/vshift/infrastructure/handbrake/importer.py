from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal, cast

from vshift.domain.transcoding_profile.enums import (
    AudioSelectionMode,
    FramerateMode,
    FrameRateType,
    QualityMode,
    SubtitleSelectionMode,
)
from vshift.domain.transcoding_profile.vshift_profile import (
    AudioTrack,
    SubtitleTrack,
    VideoProfile,
    VshiftProfile,
)


class HandBrakeImporter:
    """Parse and map HandBrake preset JSON into vshift profiles."""

    _video_encoder_map: dict[str, str] = {
        "x264": "h264",
        "x265": "h265",
        "x265_10bit": "h265",
        "x265_12bit": "h265",
        "svt_av1": "av1",
        "svt_av1_10bit": "av1",
        "svt_av1_12bit": "av1",
        "vp8": "vp8",
        "vp9": "vp9",
        "vp9_10bit": "vp9",
        "theora": "theora",
        "mpeg4": "mpeg4",
        "mpeg2": "mpeg2",
        "ffv1": "ffv1",
    }

    _format_map: dict[str, str] = {
        "mp4": "mp4",
        "av_mp4": "mp4",
        "mkv": "mkv",
        "av_mkv": "mkv",
        "webm": "webm",
        "avi": "avi",
        "mov": "mov",
    }

    def parse_preset(self, data: dict[str, Any]) -> VshiftProfile:
        hb = self._normalize_handbrake_dict(data)
        codec, bit_depth = self._map_video_encoder(str(hb.get("VideoEncoder", "x264")))
        quality_mode, quality, average_bitrate = self._parse_quality(hb)
        framerate_raw = str(hb.get("VideoFramerate", "auto"))
        frame_rate_type, frame_rate = self._parse_framerate(framerate_raw)

        try:
            framerate_mode = FramerateMode(str(hb.get("VideoFramerateMode", "vfr")))
        except ValueError:
            framerate_mode = FramerateMode.VFR

        audio_list = hb.get("AudioList", [])
        audio_tracks: list[AudioTrack] = []
        if isinstance(audio_list, list):
            for track in cast(list[Any], audio_list):
                if isinstance(track, dict):
                    audio_tracks.append(
                        self._parse_audio_track(cast(dict[str, Any], track))
                    )
        audio_selection_mode = self._parse_audio_selection_mode(
            str(hb.get("AudioTrackSelectionBehavior", "auto"))
        )
        audio_language_list = self._parse_language_list(hb.get("AudioLanguageList", []))
        audio_passthrough = bool(hb.get("AudioCopyMask")) or any(
            track.copy_track for track in audio_tracks
        )

        subtitle_tracks = self._parse_subtitle_tracks(hb)
        subtitle_selection_mode = self._parse_subtitle_selection_mode(
            str(hb.get("SubtitleTrackSelectionBehavior", "auto"))
        )
        subtitle_language_list = self._parse_language_list(
            hb.get("SubtitleLanguageList", [])
        )
        subtitle_passthrough = bool(hb.get("SubtitleTrackNamePassthru", False)) or any(
            track.copy_track for track in subtitle_tracks
        )

        return VshiftProfile(
            name=str(hb.get("PresetName", "Unnamed")),
            description=str(hb.get("PresetDescription") or ""),
            format=self._map_container_format(str(hb.get("FileFormat", "mp4"))),
            video=VideoProfile(
                codec=codec,
                bit_depth=bit_depth,
                frame_rate_type=frame_rate_type,
                frame_rate=frame_rate,
                framerate_mode=framerate_mode,
                width=self._parse_dimension(hb.get("PictureWidth")),
                height=self._parse_dimension(hb.get("PictureHeight")),
                quality_mode=quality_mode,
                quality=quality,
                average_bitrate=average_bitrate,
                encoder_preset=str(hb.get("VideoPreset", "medium")),
                encoder_tune=str(hb.get("VideoTune", "")),
                encoder_profile=str(hb.get("VideoProfile", "auto")),
                encoder_level=str(hb.get("VideoLevel", "auto")),
                multi_pass=bool(hb.get("VideoMultiPass", False)),
                turbo_multi_pass=bool(hb.get("VideoTurboMultiPass", False)),
                grayscale=bool(hb.get("VideoGrayScale", False)),
            ),
            audio_tracks=audio_tracks,
            audio_selection_mode=audio_selection_mode,
            audio_language_list=audio_language_list,
            audio_passthrough=audio_passthrough,
            subtitle_tracks=subtitle_tracks,
            subtitle_selection_mode=subtitle_selection_mode,
            subtitle_language_list=subtitle_language_list,
            subtitle_passthrough=subtitle_passthrough,
            chapter_markers=bool(hb.get("ChapterMarkers", True)),
            optimize=bool(hb.get("Optimize", False)),
        )

    def parse_presets_from_json(self, data: str | bytes) -> list[VshiftProfile]:
        parsed = json.loads(data)
        roots = self._handbrake_root_nodes(parsed)
        leaves = self._iter_handbrake_leaf_presets(roots)
        return [self.parse_preset(leaf) for leaf in leaves]

    def parse_presets_from_file(self, path: Path) -> list[VshiftProfile]:
        return self.parse_presets_from_json(path.read_text(encoding="utf-8"))

    def _normalize_handbrake_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(data)
        if "VideoTwoPass" in normalized and "VideoMultiPass" not in normalized:
            normalized["VideoMultiPass"] = normalized["VideoTwoPass"]
        if (
            "VideoTurboTwoPass" in normalized
            and "VideoTurboMultiPass" not in normalized
        ):
            normalized["VideoTurboMultiPass"] = normalized["VideoTurboTwoPass"]
        if "Mp4HttpOptimize" in normalized and "Optimize" not in normalized:
            normalized["Optimize"] = normalized["Mp4HttpOptimize"]
        return normalized

    def _handbrake_root_nodes(self, parsed: Any) -> list[dict[str, Any]]:
        if isinstance(parsed, list):
            return [
                cast(dict[str, Any], node)
                for node in cast(list[Any], parsed)
                if isinstance(node, dict)
            ]
        if isinstance(parsed, dict):
            parsed_dict = cast(dict[str, Any], parsed)
            preset_list = parsed_dict.get("PresetList")
            if isinstance(preset_list, list):
                return [
                    cast(dict[str, Any], node)
                    for node in cast(list[Any], preset_list)
                    if isinstance(node, dict)
                ]
        msg = "Unrecognized HandBrake preset document structure"
        raise ValueError(msg)

    def _iter_handbrake_leaf_presets(
        self, nodes: list[dict[str, Any]]
    ) -> Iterator[dict[str, Any]]:
        for raw_node in nodes:
            node = self._normalize_handbrake_dict(raw_node)
            if node.get("Folder", False):
                children = node.get("ChildrenArray", [])
                if isinstance(children, list):
                    child_dicts = [
                        cast(dict[str, Any], child)
                        for child in cast(list[Any], children)
                        if isinstance(child, dict)
                    ]
                    yield from self._iter_handbrake_leaf_presets(child_dicts)
            else:
                yield node

    def _map_bit_depth(self, encoder: str) -> Literal[8, 10, 12]:
        if "12bit" in encoder:
            return 12
        if "10bit" in encoder:
            return 10
        return 8

    def _map_video_encoder(self, encoder: str) -> tuple[str, Literal[8, 10, 12]]:
        mapped = self._video_encoder_map.get(encoder, encoder)
        return mapped, self._map_bit_depth(encoder)

    def _map_container_format(self, file_format: str) -> str:
        return self._format_map.get(file_format, file_format)

    def _parse_dimension(self, value: Any) -> int | None:
        if value is None or value == 0:
            return None
        if isinstance(value, int):
            return value
        return None

    def _parse_framerate(self, framerate: str) -> tuple[FrameRateType, float | None]:
        if framerate in ("auto", ""):
            return FrameRateType.SAME_AS_SOURCE, None
        try:
            return FrameRateType.CUSTOM, float(framerate)
        except ValueError:
            return FrameRateType.SAME_AS_SOURCE, None

    def _parse_quality(
        self, hb: dict[str, Any]
    ) -> tuple[QualityMode, float, int | None]:
        quality_type = int(hb.get("VideoQualityType", 2))
        slider = float(hb.get("VideoQualitySlider", 22.0))
        avg_bitrate = hb.get("VideoAvgBitrate")
        bitrate_kbps = int(avg_bitrate) if avg_bitrate is not None else None

        if quality_type == 1:
            return QualityMode.AVERAGE_BITRATE, slider, bitrate_kbps
        if quality_type == 2:
            return QualityMode.CONSTANT, slider, None
        if slider >= 0:
            return QualityMode.CONSTANT, slider, None
        return QualityMode.AVERAGE_BITRATE, slider, bitrate_kbps

    def _parse_audio_track(self, entry: dict[str, Any]) -> AudioTrack:
        encoder = str(entry.get("AudioEncoder", "aac"))
        copy_track = encoder == "copy" or encoder.startswith("copy:")
        codec = encoder.removeprefix("copy:") if copy_track else encoder

        samplerate_raw = entry.get("AudioSamplerate", "auto")
        sample_rate: int | None = None
        if samplerate_raw not in ("auto", "", None):
            try:
                sample_rate = int(samplerate_raw)
            except (TypeError, ValueError):
                sample_rate = None

        return AudioTrack(
            codec=codec,
            bit_rate=int(entry.get("AudioBitrate", 160)),
            sample_rate=sample_rate,
            mixdown=str(entry.get("AudioMixdown", "stereo")),
            copy_track=copy_track,
        )

    def _parse_audio_selection_mode(self, value: str) -> AudioSelectionMode:
        mapping = {
            "auto": AudioSelectionMode.AUTO,
            "first": AudioSelectionMode.FIRST,
            "all": AudioSelectionMode.ALL,
            "none": AudioSelectionMode.NONE,
        }
        return mapping.get(value, AudioSelectionMode.AUTO)

    def _parse_subtitle_selection_mode(self, value: str) -> SubtitleSelectionMode:
        mapping = {
            "auto": SubtitleSelectionMode.AUTO,
            "first": SubtitleSelectionMode.FIRST,
            "all": SubtitleSelectionMode.ALL,
            "none": SubtitleSelectionMode.NONE,
            "foreign": SubtitleSelectionMode.FOREIGN,
        }
        return mapping.get(value, SubtitleSelectionMode.AUTO)

    def _parse_language_list(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in cast(list[Any], value)]

    def _parse_subtitle_tracks(self, hb: dict[str, Any]) -> list[SubtitleTrack]:
        language_list = self._parse_language_list(hb.get("SubtitleLanguageList", []))
        if not language_list:
            return []
        burn_behavior = str(hb.get("SubtitleBurnBehavior", "none"))
        return [
            SubtitleTrack(
                language=language,
                codec="copy",
                copy_track=True,
                burn_in=(burn_behavior in {"all", "foreign"}),
                is_default=(index == 0),
            )
            for index, language in enumerate(language_list)
        ]

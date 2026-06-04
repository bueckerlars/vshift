import subprocess
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import UUID

import ffmpeg
import pytest
from ffmpeg.exceptions import FFMpegExecuteError

from vshift.domain.job.job_state import JobState
from vshift.domain.job.transcode_job import TranscodeJob
from vshift.domain.transcoding_profile import VshiftProfile
from vshift.domain.transcoding_profile.enums import QualityMode, VideoEncoder
from vshift.exception import VShiftException
from vshift.infrastructure.ffmpeg.command_builder import FfmpegCommandBuilder
from vshift.infrastructure.ffmpeg.encoder_resolver import EncoderResolver
from vshift.infrastructure.ffmpeg.probe import FfmpegProbe
from vshift.infrastructure.ffmpeg.profile_mapper import ProfileMapper


def _sample_profile(*, encoder: VideoEncoder = VideoEncoder.AUTO) -> VshiftProfile:
    return VshiftProfile.model_validate(
        {
            "name": "H.264 1080p",
            "format": "mp4",
            "video": {
                "codec": "h264",
                "encoder": encoder.value,
                "quality_mode": QualityMode.CONSTANT.value,
                "quality": 22.0,
                "width": 1920,
                "height": 1080,
                "encoder_preset": "medium",
            },
            "audio_tracks": [
                {"codec": "aac", "bit_rate": 160, "mixdown": "stereo"},
            ],
            "optimize": True,
        }
    )


def _sample_job(profile: VshiftProfile) -> TranscodeJob:
    return TranscodeJob(
        id=UUID("00000000-0000-4000-8000-000000000001"),
        input_path=Path("/data/input/movie.mkv"),
        output_path=Path("/data/output/movie.mp4"),
        profile_name="h264_1080p",
        profile_snapshot=profile,
        state=JobState.PENDING,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        match_rule_id="default",
    )


def test_encoder_resolver_prefers_hardware_for_auto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "vshift.infrastructure.ffmpeg.encoder_resolver.EncoderResolver._nvidia_gpu_available",
        lambda: True,
    )
    resolver = EncoderResolver(
        available_encoders={"h264_nvenc", "libx264"},
    )
    profile = _sample_profile()

    assert resolver.resolve(profile.video) == VideoEncoder.H264_NVENC


def test_encoder_resolver_skips_qsv_without_gpu_device(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "vshift.infrastructure.ffmpeg.encoder_resolver.EncoderResolver._intel_gpu_available",
        lambda: False,
    )
    resolver = EncoderResolver(
        available_encoders={"h264_qsv", "libx264"},
    )
    profile = _sample_profile()

    assert resolver.resolve(profile.video) == VideoEncoder.LIBX264


def test_encoder_resolver_prefers_qsv_when_gpu_device_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "vshift.infrastructure.ffmpeg.encoder_resolver.EncoderResolver._intel_gpu_available",
        lambda: True,
    )
    resolver = EncoderResolver(
        available_encoders={"h264_qsv", "libx264"},
    )
    profile = _sample_profile()

    assert resolver.resolve(profile.video) == VideoEncoder.H264_QSV


def test_encoder_resolver_uses_explicit_encoder() -> None:
    resolver = EncoderResolver(available_encoders={"libx264"})
    profile = _sample_profile(encoder=VideoEncoder.LIBX264)

    assert resolver.resolve(profile.video) == VideoEncoder.LIBX264


def test_profile_mapper_builds_scale_and_quality_args() -> None:
    mapped = ProfileMapper().map_profile(
        _sample_profile(),
        video_encoder=VideoEncoder.LIBX264,
    )

    assert "-crf" in mapped.video_args
    assert "22" in mapped.video_args
    assert mapped.video_filter == "scale=1920:1080"
    assert "-movflags" in mapped.output_args


def test_probe_maps_typed_ffprobe_result(tmp_path: Path) -> None:
    media_path = tmp_path / "movie.mkv"
    media_path.write_bytes(b"fake-media")

    probe_result = SimpleNamespace(
        format=SimpleNamespace(size=12345, duration=3600.5),
        streams=SimpleNamespace(
            stream=(
                SimpleNamespace(
                    codec_type="video",
                    codec_name="h264",
                    width=1920,
                    height=1080,
                    pix_fmt="yuv420p",
                    color_transfer="bt709",
                    color_primaries="bt709",
                    side_data_list=None,
                ),
            ),
        ),
    )

    with patch.object(ffmpeg, "probe_obj", return_value=probe_result):
        result = FfmpegProbe().probe(media_path)

    assert result.size_bytes == 12345
    assert result.duration_seconds == 3600.5
    assert result.video_codec == "h264"
    assert result.width == 1920
    assert result.height == 1080
    assert result.bit_depth == 8
    assert result.hdr is False


def test_probe_wraps_ffprobe_execute_error(tmp_path: Path) -> None:
    media_path = tmp_path / "movie.mkv"
    media_path.write_bytes(b"fake-media")
    ffmpeg_error = FFMpegExecuteError(
        retcode=1,
        cmd="ffprobe movie.mkv",
        stdout=b"",
        stderr=b"invalid data",
    )

    with (
        patch.object(ffmpeg, "probe_obj", side_effect=ffmpeg_error),
        pytest.raises(VShiftException, match="ffprobe failed"),
    ):
        FfmpegProbe().probe(media_path)


def test_probe_integration_with_real_ffprobe(tmp_path: Path) -> None:
    if subprocess.run(["ffmpeg", "-version"], capture_output=True).returncode != 0:
        pytest.skip("ffmpeg not available")

    media_path = tmp_path / "sample.mp4"
    completed = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=red:s=128x72:d=1",
            "-c:v",
            "libx264",
            str(media_path),
        ],
        capture_output=True,
    )
    if completed.returncode != 0:
        pytest.skip("ffmpeg could not create sample media")

    result = FfmpegProbe().probe(media_path)

    assert result.size_bytes > 0
    assert result.duration_seconds is not None
    assert 0.9 <= result.duration_seconds <= 1.1
    assert result.video_codec == "h264"
    assert result.width == 128
    assert result.height == 72


def test_profile_mapper_applies_libx265_preset() -> None:
    profile = VshiftProfile.model_validate(
        {
            "name": "HEVC",
            "format": "mkv",
            "video": {
                "codec": "h265",
                "encoder": "libx265",
                "quality_mode": "constant",
                "quality": 22.0,
                "encoder_preset": "slower",
                "bit_depth": 10,
            },
        }
    )
    mapped = ProfileMapper().map_profile(profile, video_encoder=VideoEncoder.LIBX265)

    assert "-preset" in mapped.video_args
    assert "slower" in mapped.video_args
    assert "yuv420p10le" in mapped.video_args


def test_command_builder_maps_mkv_to_matroska_muxer() -> None:
    profile = VshiftProfile.model_validate(
        {
            "name": "HEVC MKV",
            "format": "mkv",
            "video": {
                "codec": "h265",
                "encoder": "libx265",
                "quality_mode": "constant",
                "quality": 22.0,
            },
        }
    )
    builder = FfmpegCommandBuilder(
        encoder_resolver=EncoderResolver(available_encoders={"libx265"}),
    )
    command = builder.build(
        _sample_job(profile),
        output_path=Path("/data/temp/job.partial.mkv"),
    )

    format_index = command.index("-f")
    assert command[format_index + 1] == "matroska"


def test_command_builder_adds_thread_limit_when_configured() -> None:
    builder = FfmpegCommandBuilder(
        encoder_resolver=EncoderResolver(available_encoders={"libx264"}),
        thread_count=4,
    )
    command = builder.build(
        _sample_job(_sample_profile(encoder=VideoEncoder.LIBX264)),
        output_path=Path("/data/temp/job.partial.mp4"),
    )

    threads_index = command.index("-threads")
    assert command[threads_index + 1] == "4"


def test_command_builder_assembles_ffmpeg_argv() -> None:
    builder = FfmpegCommandBuilder(
        encoder_resolver=EncoderResolver(available_encoders={"libx264"}),
    )
    command = builder.build(
        _sample_job(_sample_profile(encoder=VideoEncoder.LIBX264)),
        output_path=Path("/data/temp/job.partial.mp4"),
    )

    assert command[0] == "ffmpeg"
    assert "-i" in command
    assert "/data/input/movie.mkv" in command
    assert "-c:v" in command
    assert "libx264" in command
    assert "-vf" in command
    assert "scale=1920:1080" in command
    assert command[-1] == "/data/temp/job.partial.mp4"

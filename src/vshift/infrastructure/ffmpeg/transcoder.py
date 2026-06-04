from __future__ import annotations

import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from vshift.domain.job.job_summary import JobSummary
from vshift.domain.job.transcode_job import TranscodeJob
from vshift.domain.transcoding.transcode_result import TranscodeResult
from vshift.domain.transcoding_profile.enums import VideoEncoder
from vshift.exception import VShiftException
from vshift.infrastructure.ffmpeg.command_builder import FfmpegCommandBuilder
from vshift.infrastructure.ffmpeg.encoder_resolver import EncoderResolver
from vshift.infrastructure.ffmpeg.models import FfmpegPaths
from vshift.infrastructure.ffmpeg.probe import FfmpegProbe
from vshift.infrastructure.ffmpeg.version import ffmpeg_version

_HARDWARE_ENCODER_FAILURE_MARKERS = (
    "Error creating a MFX session",
    "Cannot load libcuda",
    "Cannot load nvcuda",
    "Failed to initialise VAAPI",
    "No VA display",
    "Error while opening encoder",
)


class FfmpegTranscoder:
    """Executes FFmpeg transcoding and builds job summaries."""

    def __init__(
        self,
        *,
        paths: FfmpegPaths | None = None,
        command_builder: FfmpegCommandBuilder | None = None,
        probe: FfmpegProbe | None = None,
        temp_dir: Path | None = None,
    ) -> None:
        self._paths = paths or FfmpegPaths()
        self._command_builder = command_builder or FfmpegCommandBuilder(
            paths=self._paths
        )
        self._probe = probe or FfmpegProbe(self._paths)
        self._temp_dir = temp_dir

    def transcode(self, job: TranscodeJob) -> TranscodeResult:
        if not job.input_path.is_file():
            msg = f"input file not found: {job.input_path}"
            raise VShiftException(msg)

        output_path = job.output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_output = self._temporary_output_path(job)

        if temp_output.exists():
            temp_output.unlink()

        profile = job.profile_snapshot
        video_encoder = self._command_builder.resolve_encoder(job)
        command = self._command_builder.build(
            job,
            output_path=temp_output,
            video_encoder=video_encoder,
        )
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0 and self._should_retry_with_software(
            completed.stderr,
            video_encoder=video_encoder,
            profile_encoder=profile.video.encoder,
        ):
            fallback = self._command_builder.software_fallback(profile.video.codec)
            if temp_output.exists():
                temp_output.unlink()
            command = self._command_builder.build(
                job,
                output_path=temp_output,
                video_encoder=fallback,
            )
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
            )
            video_encoder = fallback

        wall_clock_seconds = time.perf_counter() - started

        if completed.returncode != 0:
            if temp_output.exists():
                temp_output.unlink()
            msg = f"ffmpeg failed for job {job.id}: {completed.stderr.strip()}"
            raise VShiftException(msg)

        temp_output.replace(output_path)

        output_probe = self._probe.probe(output_path)
        video_codec_out = job.profile_snapshot.video.codec
        resolution_out = _format_resolution(output_probe.width, output_probe.height)

        return TranscodeResult(
            output_path=output_path,
            wall_clock_seconds=wall_clock_seconds,
            ffmpeg_version=ffmpeg_version(self._paths.ffmpeg),
            video_codec_out=video_codec_out,
            resolution_out=resolution_out,
        )

    def build_summary(
        self,
        job: TranscodeJob,
        result: TranscodeResult,
    ) -> JobSummary:
        input_probe = self._probe.probe(job.input_path)
        output_probe = self._probe.probe(result.output_path)
        completed_at = datetime.now(tz=UTC)
        started_at = completed_at - timedelta(seconds=result.wall_clock_seconds)

        compression_ratio: float | None = None
        if output_probe.size_bytes > 0:
            compression_ratio = input_probe.size_bytes / output_probe.size_bytes

        return JobSummary(
            job_id=job.id,
            input_path=job.input_path,
            output_path=result.output_path,
            profile_name=job.profile_name,
            input_size_bytes=input_probe.size_bytes,
            output_size_bytes=output_probe.size_bytes,
            input_duration_seconds=input_probe.duration_seconds,
            compression_ratio=compression_ratio,
            wall_clock_seconds=result.wall_clock_seconds,
            ffmpeg_version=result.ffmpeg_version,
            started_at=started_at,
            completed_at=completed_at,
            video_codec_in=input_probe.video_codec,
            video_codec_out=result.video_codec_out,
            resolution_in=_format_resolution(input_probe.width, input_probe.height),
            resolution_out=result.resolution_out,
        )

    def _temporary_output_path(self, job: TranscodeJob) -> Path:
        temp_dir = self._temp_dir or job.output_path.parent
        temp_dir.mkdir(parents=True, exist_ok=True)
        suffix = job.output_path.suffix or f".{job.profile_snapshot.format}"
        return temp_dir / f"{job.id}{suffix}.partial"

    @staticmethod
    def _should_retry_with_software(
        stderr: str,
        *,
        video_encoder: VideoEncoder,
        profile_encoder: VideoEncoder,
    ) -> bool:
        if profile_encoder != VideoEncoder.AUTO:
            return False
        if not EncoderResolver.is_hardware_encoder(video_encoder):
            return False
        return any(marker in stderr for marker in _HARDWARE_ENCODER_FAILURE_MARKERS)


def _format_resolution(width: int | None, height: int | None) -> str | None:
    if width is None or height is None:
        return None
    return f"{width}x{height}"

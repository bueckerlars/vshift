from __future__ import annotations

import re
import subprocess
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from vshift.domain.job.job_summary import JobSummary
from vshift.domain.job.transcode_job import TranscodeJob
from vshift.domain.transcoding.transcode_result import TranscodeResult
from vshift.exception import VShiftException
from vshift.infrastructure.ffmpeg.command_builder import FfmpegCommandBuilder
from vshift.infrastructure.ffmpeg.models import FfmpegPaths
from vshift.infrastructure.ffmpeg.probe import FfmpegProbe


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

        command = self._command_builder.build(job, output_path=temp_output)
        started = time.perf_counter()
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )
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
            ffmpeg_version=_ffmpeg_version(self._paths.ffmpeg),
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


def _format_resolution(width: int | None, height: int | None) -> str | None:
    if width is None or height is None:
        return None
    return f"{width}x{height}"


def _ffmpeg_version(ffmpeg_path: str) -> str:
    completed = subprocess.run(
        [ffmpeg_path, "-version"],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        return "unknown"

    first_line = completed.stdout.splitlines()
    if not first_line:
        return "unknown"

    match = re.search(r"ffmpeg version (\S+)", first_line[0])
    if match is None:
        return "unknown"
    return match.group(1)

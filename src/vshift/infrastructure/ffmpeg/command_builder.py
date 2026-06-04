from pathlib import Path

from vshift.domain.job.transcode_job import TranscodeJob
from vshift.domain.transcoding_profile.enums import VideoEncoder
from vshift.infrastructure.ffmpeg.container_format import ffmpeg_muxer_format
from vshift.infrastructure.ffmpeg.encoder_resolver import EncoderResolver
from vshift.infrastructure.ffmpeg.models import FfmpegPaths
from vshift.infrastructure.ffmpeg.profile_mapper import ProfileMapper


class FfmpegCommandBuilder:
    """Builds FFmpeg argv lists for transcoding jobs."""

    def __init__(
        self,
        encoder_resolver: EncoderResolver | None = None,
        profile_mapper: ProfileMapper | None = None,
        paths: FfmpegPaths | None = None,
    ) -> None:
        self._paths = paths or FfmpegPaths()
        self._encoder_resolver = encoder_resolver or EncoderResolver(self._paths)
        self._profile_mapper = profile_mapper or ProfileMapper()

    def resolve_encoder(self, job: TranscodeJob) -> VideoEncoder:
        return self._encoder_resolver.resolve(job.profile_snapshot.video)

    def software_fallback(self, codec: str) -> VideoEncoder:
        return self._encoder_resolver.software_fallback(codec)

    def build(
        self,
        job: TranscodeJob,
        *,
        output_path: Path,
        video_encoder: VideoEncoder | None = None,
    ) -> list[str]:
        profile = job.profile_snapshot
        resolved_encoder = video_encoder or self.resolve_encoder(job)
        mapped = self._profile_mapper.map_profile(
            profile,
            video_encoder=resolved_encoder,
        )

        command: list[str] = [
            self._paths.ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-y",
        ]
        command.extend(mapped.input_args)
        command.extend(["-i", str(job.input_path)])
        command.extend(mapped.maps)
        command.extend(mapped.video_args)
        if mapped.video_filter is not None:
            command.extend(["-vf", mapped.video_filter])
        command.extend(mapped.audio_args)
        command.extend(mapped.output_args)
        command.extend(["-f", ffmpeg_muxer_format(profile.format), str(output_path)])
        return command

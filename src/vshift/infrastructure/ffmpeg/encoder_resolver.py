from __future__ import annotations

import subprocess

from ffmpeg_core.info import get_coders  # pyright: ignore[reportMissingTypeStubs]

from vshift.domain.transcoding_profile.enums import VideoEncoder
from vshift.domain.transcoding_profile.vshift_profile import VideoProfile
from vshift.exception import VShiftException
from vshift.infrastructure.ffmpeg.models import FfmpegPaths


class EncoderResolver:
    """Resolves FFmpeg video encoders from profile settings and host capabilities."""

    _CODEC_ENCODER_PRIORITY: dict[str, list[VideoEncoder]] = {
        "h264": [
            VideoEncoder.H264_VIDEOTOOLBOX,
            VideoEncoder.H264_NVENC,
            VideoEncoder.H264_QSV,
            VideoEncoder.H264_VAAPI,
            VideoEncoder.LIBX264,
        ],
        "h265": [
            VideoEncoder.HEVC_VIDEOTOOLBOX,
            VideoEncoder.HEVC_NVENC,
            VideoEncoder.HEVC_QSV,
            VideoEncoder.HEVC_VAAPI,
            VideoEncoder.LIBX265,
        ],
        "hevc": [
            VideoEncoder.HEVC_VIDEOTOOLBOX,
            VideoEncoder.HEVC_NVENC,
            VideoEncoder.HEVC_QSV,
            VideoEncoder.HEVC_VAAPI,
            VideoEncoder.LIBX265,
        ],
        "av1": [
            VideoEncoder.AV1_NVENC,
            VideoEncoder.LIBSVTAV1,
        ],
    }

    _SOFTWARE_FALLBACK: dict[str, VideoEncoder] = {
        "h264": VideoEncoder.LIBX264,
        "h265": VideoEncoder.LIBX265,
        "hevc": VideoEncoder.LIBX265,
        "av1": VideoEncoder.LIBSVTAV1,
    }

    def __init__(
        self,
        paths: FfmpegPaths | None = None,
        available_encoders: set[str] | None = None,
    ) -> None:
        self._paths = paths or FfmpegPaths()
        self._available_encoders = (
            available_encoders
            if available_encoders is not None
            else self._detect_available_encoders()
        )

    def resolve(self, video: VideoProfile) -> VideoEncoder:
        if video.encoder != VideoEncoder.AUTO:
            if video.encoder.value not in self._available_encoders:
                msg = f"encoder '{video.encoder.value}' is not available in ffmpeg"
                raise VShiftException(msg)
            return video.encoder

        codec = video.codec.lower()
        for encoder in self._CODEC_ENCODER_PRIORITY.get(codec, []):
            if encoder.value in self._available_encoders:
                return encoder

        fallback = self._SOFTWARE_FALLBACK.get(codec)
        if fallback is not None and fallback.value in self._available_encoders:
            return fallback

        msg = f"no available ffmpeg encoder found for codec '{video.codec}'"
        raise VShiftException(msg)

    def list_available_encoders(self) -> set[str]:
        return set(self._available_encoders)

    def _detect_available_encoders(self) -> set[str]:
        command = [
            self._paths.ffmpeg,
            "-hide_banner",
            "-encoders",
        ]
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.decode(errors="replace").strip()
            msg = f"failed to list ffmpeg encoders: {stderr}"
            raise VShiftException(msg)

        coders = get_coders(completed.stdout.decode(errors="replace"))
        return {coder.name for coder in coders if coder.flags.video}

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MediaProbe:
    size_bytes: int
    duration_seconds: float | None
    video_codec: str | None
    width: int | None
    height: int | None
    bit_depth: int | None
    hdr: bool | None


@dataclass(frozen=True, slots=True)
class FfmpegPaths:
    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"

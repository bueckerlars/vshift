"""Maps vshift container names to FFmpeg -f format identifiers."""

from __future__ import annotations

# Profile/container names (HandBrake-style) -> ffmpeg -f muxer names.
_FFMPEG_MUXER_FORMATS: dict[str, str] = {
    "mkv": "matroska",
    "mp4": "mp4",
    "webm": "webm",
    "avi": "avi",
    "mov": "mov",
}


def ffmpeg_muxer_format(container_format: str) -> str:
    """Return the FFmpeg muxer name for a profile container format."""
    return _FFMPEG_MUXER_FORMATS.get(container_format.lower(), container_format)

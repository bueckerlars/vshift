from __future__ import annotations

from pathlib import Path
from typing import Protocol, cast

from vshift.exception import VShiftException
from vshift.infrastructure.ffmpeg._python_ffmpeg import FFMpegExecuteError, ffmpeg
from vshift.infrastructure.ffmpeg.models import FfmpegPaths, MediaProbe
from vshift.infrastructure.ffmpeg.video_stream_info import parse_video_stream


class _ProbeFormat(Protocol):
    size: int | None
    duration: float | None


class _ProbeStream(Protocol):
    codec_type: str | None
    codec_name: str | None
    width: int | None
    height: int | None
    pix_fmt: str | None
    color_transfer: str | None
    color_primaries: str | None
    side_data_list: list[dict[str, object]] | None


class _ProbeStreams(Protocol):
    stream: tuple[_ProbeStream, ...] | None


class _ProbeResult(Protocol):
    format: _ProbeFormat | None
    streams: _ProbeStreams | None


class FfmpegProbe:
    """Reads media metadata via ffprobe."""

    def __init__(self, paths: FfmpegPaths | None = None) -> None:
        self._paths = paths or FfmpegPaths()

    def probe(self, path: Path) -> MediaProbe:
        if not path.is_file():
            msg = f"media file not found: {path}"
            raise VShiftException(msg)

        try:
            result = ffmpeg.probe_obj(path, cmd=self._paths.ffprobe)
        except FFMpegExecuteError as error:
            msg = f"ffprobe failed for {path}: {_format_stderr(error)}"
            raise VShiftException(msg) from error

        if result is None:
            msg = f"unexpected empty ffprobe response for {path}"
            raise VShiftException(msg)

        return _to_media_probe(cast(_ProbeResult, result), path)


def _format_stderr(error: FFMpegExecuteError) -> str:
    return error.stderr.decode(errors="replace").strip()


def _to_media_probe(result: _ProbeResult, path: Path) -> MediaProbe:
    format_size = 0
    duration_seconds: float | None = None
    if result.format is not None:
        if result.format.size is not None and result.format.size > 0:
            format_size = result.format.size
        duration_seconds = result.format.duration

    if format_size <= 0:
        format_size = path.stat().st_size

    video_codec: str | None = None
    width: int | None = None
    height: int | None = None
    bit_depth: int | None = None
    hdr: bool | None = None
    if result.streams is not None and result.streams.stream is not None:
        for stream in result.streams.stream:
            if stream.codec_type != "video":
                continue
            stream_dict = _stream_to_dict(stream)
            video_info = parse_video_stream(stream_dict)
            video_codec = video_info.codec_name
            width = video_info.width
            height = video_info.height
            bit_depth = video_info.bit_depth
            hdr = video_info.hdr
            break

    return MediaProbe(
        size_bytes=format_size,
        duration_seconds=duration_seconds,
        video_codec=video_codec,
        width=width,
        height=height,
        bit_depth=bit_depth,
        hdr=hdr,
    )


def _stream_to_dict(stream: _ProbeStream) -> dict[str, object]:
    payload: dict[str, object] = {
        "codec_type": stream.codec_type,
        "codec_name": stream.codec_name,
        "width": stream.width,
        "height": stream.height,
        "pix_fmt": stream.pix_fmt,
        "color_transfer": stream.color_transfer,
        "color_primaries": stream.color_primaries,
    }
    if stream.side_data_list is not None:
        payload["side_data_list"] = stream.side_data_list
    return payload

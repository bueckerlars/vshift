from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast


@dataclass(frozen=True, slots=True)
class VideoStreamInfo:
    codec_name: str | None
    width: int | None
    height: int | None
    bit_depth: int
    hdr: bool


_HDR_TRANSFERS = frozenset({"smpte2084", "arib-std-b67"})
_HDR_PRIMARIES = frozenset({"bt2020", "bt2020nc"})
_SDR_TRANSFERS = frozenset({"bt709", "bt601", "smpte170m", "iec61966-2-1"})


def parse_video_stream(stream: dict[str, Any]) -> VideoStreamInfo:
    pix_fmt = stream.get("pix_fmt")
    bit_depth = bit_depth_from_pix_fmt(pix_fmt if isinstance(pix_fmt, str) else None)
    hdr = is_hdr_stream(stream, bit_depth=bit_depth)

    width = stream.get("width")
    height = stream.get("height")
    codec_name = stream.get("codec_name")

    return VideoStreamInfo(
        codec_name=codec_name if isinstance(codec_name, str) else None,
        width=width if isinstance(width, int) else None,
        height=height if isinstance(height, int) else None,
        bit_depth=bit_depth,
        hdr=hdr,
    )


def bit_depth_from_pix_fmt(pix_fmt: str | None) -> int:
    if not pix_fmt:
        return 8
    lowered = pix_fmt.lower()
    if "12" in lowered:
        return 12
    if "10" in lowered or lowered in {"p010le", "p010be"}:
        return 10
    return 8


def is_hdr_stream(stream: dict[str, Any], *, bit_depth: int) -> bool:
    transfer = _normalize_color_value(stream.get("color_transfer"))
    primaries = _normalize_color_value(stream.get("color_primaries"))

    if transfer in _HDR_TRANSFERS:
        return True
    if primaries in _HDR_PRIMARIES and transfer not in _SDR_TRANSFERS:
        return True

    side_data_raw = stream.get("side_data_list")
    if isinstance(side_data_raw, list):
        for raw_entry in cast(list[Any], side_data_raw):
            if not isinstance(raw_entry, dict):
                continue
            entry = cast(dict[str, Any], raw_entry)
            if entry.get("side_data_type") == "HDR Dynamic Metadata":
                return True

    return bit_depth >= 10 and primaries in _HDR_PRIMARIES


def _normalize_color_value(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.lower().strip()

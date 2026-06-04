from vshift.infrastructure.ffmpeg.video_stream_info import (
    bit_depth_from_pix_fmt,
    is_hdr_stream,
    parse_video_stream,
)


def test_bit_depth_from_pix_fmt() -> None:
    assert bit_depth_from_pix_fmt("yuv420p") == 8
    assert bit_depth_from_pix_fmt("yuv420p10le") == 10
    assert bit_depth_from_pix_fmt("p010le") == 10
    assert bit_depth_from_pix_fmt("yuv420p12le") == 12


def test_is_hdr_stream_detects_pq_transfer() -> None:
    stream = {
        "pix_fmt": "yuv420p10le",
        "color_transfer": "smpte2084",
        "color_primaries": "bt2020",
    }
    assert is_hdr_stream(stream, bit_depth=10) is True


def test_is_hdr_stream_detects_sdr() -> None:
    stream = {
        "pix_fmt": "yuv420p",
        "color_transfer": "bt709",
        "color_primaries": "bt709",
    }
    assert is_hdr_stream(stream, bit_depth=8) is False


def test_parse_video_stream_maps_dimensions_and_hdr() -> None:
    info = parse_video_stream(
        {
            "codec_name": "hevc",
            "width": 3840,
            "height": 2160,
            "pix_fmt": "yuv420p10le",
            "color_transfer": "smpte2084",
            "color_primaries": "bt2020",
        }
    )

    assert info.codec_name == "hevc"
    assert info.width == 3840
    assert info.height == 2160
    assert info.bit_depth == 10
    assert info.hdr is True

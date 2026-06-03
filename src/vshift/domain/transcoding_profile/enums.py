from enum import StrEnum


class FrameRateType(StrEnum):
    SAME_AS_SOURCE = "same_as_source"
    CUSTOM = "custom"


class QualityMode(StrEnum):
    CONSTANT = "constant"
    AVERAGE_BITRATE = "average_bitrate"


class FramerateMode(StrEnum):
    VFR = "vfr"
    PFR = "pfr"
    CFR = "cfr"


class AudioSelectionMode(StrEnum):
    AUTO = "auto"
    FIRST = "first"
    ALL = "all"
    NONE = "none"


class SubtitleSelectionMode(StrEnum):
    AUTO = "auto"
    FIRST = "first"
    ALL = "all"
    NONE = "none"
    FOREIGN = "foreign"


class VideoEncoder(StrEnum):
    AUTO = "auto"
    # Software
    LIBX264 = "libx264"
    LIBX265 = "libx265"
    LIBSVTAV1 = "libsvtav1"
    # NVIDIA
    H264_NVENC = "h264_nvenc"
    HEVC_NVENC = "hevc_nvenc"
    AV1_NVENC = "av1_nvenc"
    # Intel QSV
    H264_QSV = "h264_qsv"
    HEVC_QSV = "hevc_qsv"
    # VAAPI (Linux)
    H264_VAAPI = "h264_vaapi"
    HEVC_VAAPI = "hevc_vaapi"
    # Apple
    H264_VIDEOTOOLBOX = "h264_videotoolbox"
    HEVC_VIDEOTOOLBOX = "hevc_videotoolbox"

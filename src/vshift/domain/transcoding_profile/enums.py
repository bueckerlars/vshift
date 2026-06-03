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

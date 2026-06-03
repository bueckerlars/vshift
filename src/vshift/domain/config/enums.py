from enum import StrEnum


class NoMatchAction(StrEnum):
    IGNORE = "ignore"
    REJECT = "reject"
    DEFAULT_PROFILE = "default_profile"


class InputAfterSuccess(StrEnum):
    KEEP = "keep"
    DELETE = "delete"
    MOVE = "move"

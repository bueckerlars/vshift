import fnmatch
from typing import Any, Self, cast

from pydantic import BaseModel, Field, field_validator, model_validator

from vshift.domain.file.probed_input import ProbedInput
from vshift.exception import VShiftException


class MatchCriteria(BaseModel):
    extensions: list[str] = Field(
        default_factory=list,
        description="File extensions without dot (e.g. mkv, mp4)",
    )
    min_width: int | None = Field(default=None, ge=1)
    max_width: int | None = Field(default=None, ge=1)
    min_height: int | None = Field(default=None, ge=1)
    max_height: int | None = Field(default=None, ge=1)
    min_bit_depth: int | None = Field(default=None, ge=8, le=12)
    max_bit_depth: int | None = Field(default=None, ge=8, le=12)
    hdr: bool | None = Field(
        default=None,
        description="Require HDR (true) or SDR (false) signaling when set",
    )
    filename_glob: str | None = Field(
        default=None,
        description="Glob pattern matched against the filename",
    )

    @field_validator("extensions", mode="before")
    @classmethod
    def normalize_extensions(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        items = cast(list[Any], value)
        return [str(item).lower().removeprefix(".") for item in items]

    @model_validator(mode="after")
    def validate_bounds(self) -> Self:
        if (
            self.min_width is not None
            and self.max_width is not None
            and self.min_width > self.max_width
        ):
            raise VShiftException("min_width cannot exceed max_width")
        if (
            self.min_height is not None
            and self.max_height is not None
            and self.min_height > self.max_height
        ):
            raise VShiftException("min_height cannot exceed max_height")
        if (
            self.min_bit_depth is not None
            and self.max_bit_depth is not None
            and self.min_bit_depth > self.max_bit_depth
        ):
            raise VShiftException("min_bit_depth cannot exceed max_bit_depth")
        return self

    def matches(self, probed: ProbedInput) -> bool:
        if self.extensions and probed.extension.lower() not in self.extensions:
            return False
        if self.filename_glob is not None and not fnmatch.fnmatch(
            probed.path.name,
            self.filename_glob,
        ):
            return False
        if not self._matches_dimension(probed.width, self.min_width, self.max_width):
            return False
        if not self._matches_dimension(
            probed.height,
            self.min_height,
            self.max_height,
        ):
            return False
        if not self._matches_dimension(
            probed.bit_depth,
            self.min_bit_depth,
            self.max_bit_depth,
        ):
            return False
        return self._matches_hdr(probed.hdr, self.hdr)

    @staticmethod
    def _matches_dimension(
        value: int | None,
        minimum: int | None,
        maximum: int | None,
    ) -> bool:
        if minimum is None and maximum is None:
            return True
        if value is None:
            return False
        if minimum is not None and value < minimum:
            return False
        return not (maximum is not None and value > maximum)

    @staticmethod
    def _matches_hdr(value: bool | None, expected: bool | None) -> bool:
        if expected is None:
            return True
        if value is None:
            return False
        return value == expected


class MatchRule(BaseModel):
    id: str = Field(min_length=1)
    priority: int = Field(default=100, ge=0)
    match: MatchCriteria
    profile: str = Field(min_length=1)

    @field_validator("id", "profile")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        if not value.strip():
            raise VShiftException("match rule id and profile must not be blank")
        return value

    def matches(self, probed: ProbedInput) -> bool:
        return self.match.matches(probed)

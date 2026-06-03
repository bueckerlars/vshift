from pathlib import Path
from typing import Self

from pydantic import BaseModel, Field, PositiveInt, model_validator

from vshift.domain.config.enums import InputAfterSuccess, NoMatchAction
from vshift.domain.config.match_rule import MatchRule
from vshift.domain.config.profile_matcher import ProfileMatcher
from vshift.domain.transcoding_profile.vshift_profile import VshiftProfile
from vshift.exception import VShiftException


class BehaviorSettings(BaseModel):
    no_match: NoMatchAction = Field(default=NoMatchAction.IGNORE)
    default_profile: str | None = Field(
        default=None,
        description="Required when no_match is default_profile",
    )
    input_after_success: InputAfterSuccess = Field(default=InputAfterSuccess.KEEP)
    input_move_dir: Path | None = Field(
        default=None,
        description="Required when input_after_success is move",
    )
    file_stability_seconds: PositiveInt = Field(default=10)
    max_retries: PositiveInt = Field(default=3)

    @model_validator(mode="after")
    def validate_behavior(self) -> Self:
        if self.no_match == NoMatchAction.DEFAULT_PROFILE and not self.default_profile:
            raise VShiftException(
                "default_profile is required when no_match is default_profile"
            )
        if (
            self.input_after_success == InputAfterSuccess.MOVE
            and self.input_move_dir is None
        ):
            raise VShiftException(
                "input_move_dir is required when input_after_success is move"
            )
        return self


class ConfigDirectories(BaseModel):
    input: Path
    output: Path
    temp: Path


class VshiftConfig(BaseModel):
    version: str = Field(default="1")
    behavior: BehaviorSettings = Field(default_factory=BehaviorSettings)
    directories: ConfigDirectories
    profiles: dict[str, VshiftProfile]
    rules: list[MatchRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_config(self) -> Self:
        if not self.profiles:
            raise VShiftException("at least one profile is required")

        if (
            self.behavior.no_match == NoMatchAction.DEFAULT_PROFILE
            and self.behavior.default_profile not in self.profiles
        ):
            raise VShiftException("default_profile must reference an existing profile")

        rule_ids = [rule.id for rule in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise VShiftException("match rule ids must be unique")

        for rule in self.rules:
            if rule.profile not in self.profiles:
                msg = f"rule '{rule.id}' references unknown profile '{rule.profile}'"
                raise VShiftException(msg)

        return self

    def create_profile_matcher(self) -> ProfileMatcher:
        return ProfileMatcher(self.rules)

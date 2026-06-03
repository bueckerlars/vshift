from dataclasses import dataclass

from vshift.domain.transcoding_profile.vshift_profile import VshiftProfile


@dataclass(frozen=True, slots=True)
class ProfileMatch:
    rule_id: str
    profile_name: str
    profile: VshiftProfile

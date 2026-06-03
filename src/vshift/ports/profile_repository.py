from typing import Protocol

from vshift.domain.transcoding_profile.vshift_profile import VshiftProfile


class ProfileRepository(Protocol):
    """Provides access to transcoding profiles."""

    def get(self, name: str) -> VshiftProfile | None: ...

    def list_names(self) -> list[str]: ...

    def save(self, profile: VshiftProfile) -> None: ...

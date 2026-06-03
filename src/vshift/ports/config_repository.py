from typing import Protocol

from vshift.domain.config.vshift_config import VshiftConfig
from vshift.domain.transcoding_profile.vshift_profile import VshiftProfile


class ConfigRepository(Protocol):
    """Loads and exposes application configuration."""

    def reload(self) -> None: ...

    def get_config(self) -> VshiftConfig: ...

    def get_profile(self, name: str) -> VshiftProfile | None: ...

    def list_profile_names(self) -> list[str]: ...

    def get_max_retries(self) -> int: ...

    def get_file_stability_seconds(self) -> int: ...

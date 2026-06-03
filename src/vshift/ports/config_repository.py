from typing import Protocol

from vshift.domain.transcoding_profile.vshift_profile import VshiftProfile


class ConfigRepository(Protocol):
    """Loads and exposes application configuration.

    Full VshiftConfig model is added in P1; the port exposes the operations
    required by use cases without coupling callers to the config file format.
    """

    def reload(self) -> None: ...

    def get_profile(self, name: str) -> VshiftProfile | None: ...

    def list_profile_names(self) -> list[str]: ...

    def get_max_retries(self) -> int: ...

    def get_file_stability_seconds(self) -> int: ...

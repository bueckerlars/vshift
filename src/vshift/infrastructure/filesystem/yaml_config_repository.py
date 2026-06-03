from pathlib import Path

from vshift.domain.config.vshift_config import VshiftConfig
from vshift.domain.transcoding_profile.vshift_profile import VshiftProfile
from vshift.infrastructure.filesystem.yaml_config_loader import YamlConfigLoader


class YamlConfigRepository:
    """File-backed configuration repository."""

    def __init__(
        self,
        config_path: Path,
        loader: YamlConfigLoader | None = None,
    ) -> None:
        self._config_path = config_path
        self._loader = loader or YamlConfigLoader()
        self._config = self._loader.load(config_path)

    def reload(self) -> None:
        self._config = self._loader.load(self._config_path)

    def get_config(self) -> VshiftConfig:
        return self._config

    def get_profile(self, name: str) -> VshiftProfile | None:
        return self._config.profiles.get(name)

    def list_profile_names(self) -> list[str]:
        return list(self._config.profiles.keys())

    def get_max_retries(self) -> int:
        return self._config.behavior.max_retries

    def get_file_stability_seconds(self) -> int:
        return self._config.behavior.file_stability_seconds

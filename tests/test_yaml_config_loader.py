from pathlib import Path

import pytest

from vshift.domain.config import VshiftConfig
from vshift.exception import VShiftException
from vshift.infrastructure.filesystem.yaml_config_loader import YamlConfigLoader
from vshift.infrastructure.filesystem.yaml_config_repository import YamlConfigRepository

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "config"
EXAMPLE_CONFIG_PATH = Path(__file__).parent.parent / "config" / "vshift.example.yaml"


def test_yaml_config_loader_loads_fixture() -> None:
    config = YamlConfigLoader().load(FIXTURES_DIR / "vshift.yaml")

    assert config.version == "1"
    assert config.behavior.file_stability_seconds == 5
    assert config.profiles["inline_profile"].name == "Inline"
    assert config.profiles["ref_profile"].name == "Referenced Profile"
    assert config.profiles["ref_profile"].video.quality == 21.0


def test_yaml_config_loader_loads_example_config() -> None:
    config = YamlConfigLoader().load(EXAMPLE_CONFIG_PATH)

    assert isinstance(config, VshiftConfig)
    assert len(config.profiles) == 2
    assert len(config.rules) == 2


def test_yaml_config_loader_missing_file_raises() -> None:
    with pytest.raises(VShiftException, match="config file not found"):
        YamlConfigLoader().load(FIXTURES_DIR / "missing.yaml")


def test_yaml_config_loader_invalid_profile_ref_raises() -> None:
    with pytest.raises(VShiftException, match="reference not found"):
        YamlConfigLoader().load(FIXTURES_DIR / "invalid_ref.yaml")


def test_yaml_config_loader_rejects_ref_with_extra_keys() -> None:
    with pytest.raises(VShiftException, match="must only contain the \\$ref key"):
        YamlConfigLoader().load(FIXTURES_DIR / "invalid_ref_keys.yaml")


def test_yaml_config_repository_exposes_config() -> None:
    repository = YamlConfigRepository(FIXTURES_DIR / "vshift.yaml")

    assert repository.get_max_retries() == 2
    assert repository.get_file_stability_seconds() == 5
    assert repository.list_profile_names() == ["inline_profile", "ref_profile"]
    assert repository.get_profile("inline_profile") is not None
    assert repository.get_profile("missing") is None

    config = repository.get_config()
    assert config.rules[0].profile == "inline_profile"


def test_yaml_config_repository_reload() -> None:
    repository = YamlConfigRepository(FIXTURES_DIR / "vshift.yaml")
    original_retries = repository.get_max_retries()

    repository.reload()

    assert repository.get_max_retries() == original_retries
    assert repository.get_config().version == "1"

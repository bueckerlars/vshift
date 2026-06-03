from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import ValidationError

from vshift.domain.config.vshift_config import VshiftConfig
from vshift.exception import VShiftException


class YamlConfigLoader:
    """Loads and validates vshift YAML configuration files."""

    def load(self, path: Path) -> VshiftConfig:
        if not path.is_file():
            msg = f"config file not found: {path}"
            raise VShiftException(msg)

        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            msg = "config root must be a mapping"
            raise VShiftException(msg)

        data = self._resolve_profile_refs(cast(dict[str, Any], raw), path.parent)
        try:
            return VshiftConfig.model_validate(data)
        except ValidationError as exc:
            msg = f"invalid configuration: {exc}"
            raise VShiftException(msg) from exc

    def _resolve_profile_refs(
        self,
        data: dict[str, Any],
        config_dir: Path,
    ) -> dict[str, Any]:
        profiles = data.get("profiles")
        if not isinstance(profiles, dict):
            return data

        resolved_profiles: dict[str, Any] = {}
        profile_items = cast(dict[str, Any], profiles)
        for name, profile_data in profile_items.items():
            resolved_profiles[name] = self._resolve_profile_entry(
                profile_data,
                config_dir,
                profile_name=name,
            )

        resolved = dict(data)
        resolved["profiles"] = resolved_profiles
        return resolved

    def _resolve_profile_entry(
        self,
        profile_data: Any,
        config_dir: Path,
        *,
        profile_name: str,
    ) -> Any:
        if not isinstance(profile_data, dict):
            return profile_data

        profile_dict = cast(dict[str, Any], profile_data)
        if "$ref" not in profile_dict:
            return profile_dict

        ref_keys = set(profile_dict.keys())
        if ref_keys != {"$ref"}:
            msg = f"profile '{profile_name}' $ref entry must only contain the $ref key"
            raise VShiftException(msg)

        ref_value = profile_dict["$ref"]
        if not isinstance(ref_value, str) or not ref_value.strip():
            msg = f"profile '{profile_name}' has an invalid $ref value"
            raise VShiftException(msg)

        ref_path = Path(ref_value)
        if not ref_path.is_absolute():
            ref_path = config_dir / ref_path

        if not ref_path.is_file():
            msg = f"profile '{profile_name}' reference not found: {ref_path}"
            raise VShiftException(msg)

        loaded = yaml.safe_load(ref_path.read_text(encoding="utf-8"))
        if not isinstance(loaded, dict):
            msg = f"profile '{profile_name}' reference must be a mapping: {ref_path}"
            raise VShiftException(msg)

        return cast(dict[str, Any], loaded)

from pathlib import Path
from typing import Any

import pytest
import yaml

from vshift.domain.config import (
    MatchRule,
    NoMatchAction,
    VshiftConfig,
)
from vshift.domain.file.probed_input import ProbedInput
from vshift.domain.transcoding_profile import QualityMode, VideoEncoder, VshiftProfile
from vshift.exception import VShiftException
from vshift.infrastructure.filesystem.yaml_config_loader import YamlConfigLoader

EXAMPLE_CONFIG_PATH = Path(__file__).parent.parent / "config" / "vshift.example.yaml"


def _sample_profile(name: str = "Test Profile") -> VshiftProfile:
    return VshiftProfile.model_validate(
        {
            "name": name,
            "format": "mp4",
            "video": {
                "codec": "h264",
                "encoder": "auto",
                "quality_mode": "constant",
                "quality": 22.0,
            },
        }
    )


def _sample_config(**overrides: Any) -> VshiftConfig:
    data: dict[str, Any] = {
        "directories": {
            "input": "/data/input",
            "output": "/data/output",
            "temp": "/data/temp",
        },
        "profiles": {
            "h264_1080p": _sample_profile("H.264 1080p").model_dump(),
            "h264_720p": _sample_profile("H.264 720p").model_dump(),
        },
        "rules": [
            {
                "id": "movies_1080p",
                "priority": 10,
                "match": {
                    "extensions": ["mkv"],
                    "min_width": 1280,
                    "filename_glob": "*.mkv",
                },
                "profile": "h264_1080p",
            },
            {
                "id": "small_files",
                "priority": 20,
                "match": {"extensions": ["mp4"], "max_width": 1280},
                "profile": "h264_720p",
            },
        ],
    }
    data.update(overrides)
    return VshiftConfig.model_validate(data)


def test_match_rule_extension() -> None:
    rule = MatchRule.model_validate(
        {
            "id": "mkv_only",
            "match": {"extensions": ["mkv"]},
            "profile": "h264_1080p",
        }
    )
    assert rule.matches(
        ProbedInput(path=Path("/data/input/movie.mkv"), extension="mkv")
    )
    assert not rule.matches(
        ProbedInput(path=Path("/data/input/movie.mp4"), extension="mp4")
    )


def test_match_rule_resolution_bounds() -> None:
    rule = MatchRule.model_validate(
        {
            "id": "1080p",
            "match": {"min_width": 1920, "max_height": 1080},
            "profile": "h264_1080p",
        }
    )
    assert rule.matches(
        ProbedInput(
            path=Path("/data/input/movie.mkv"),
            extension="mkv",
            width=1920,
            height=1080,
        )
    )
    assert not rule.matches(
        ProbedInput(
            path=Path("/data/input/movie.mkv"),
            extension="mkv",
            width=1280,
            height=720,
        )
    )
    assert not rule.matches(
        ProbedInput(
            path=Path("/data/input/movie.mkv"),
            extension="mkv",
            width=None,
            height=1080,
        )
    )


def test_match_rule_filename_glob() -> None:
    rule = MatchRule.model_validate(
        {
            "id": "pattern",
            "match": {"filename_glob": "show_*.mkv"},
            "profile": "h264_1080p",
        }
    )
    assert rule.matches(
        ProbedInput(path=Path("/data/input/show_01.mkv"), extension="mkv")
    )
    assert not rule.matches(
        ProbedInput(path=Path("/data/input/movie.mkv"), extension="mkv")
    )


def test_profile_matcher_uses_priority() -> None:
    config = _sample_config()
    matcher = config.create_profile_matcher()

    matched = matcher.match(
        ProbedInput(
            path=Path("/data/input/show.mkv"),
            extension="mkv",
            width=1920,
            height=1080,
        )
    )
    assert matched is not None
    assert matched.id == "movies_1080p"

    matched_small = matcher.match(
        ProbedInput(
            path=Path("/data/input/clip.mp4"),
            extension="mp4",
            width=1280,
            height=720,
        )
    )
    assert matched_small is not None
    assert matched_small.id == "small_files"


def test_vshift_config_requires_default_profile_reference() -> None:
    with pytest.raises(VShiftException):
        VshiftConfig.model_validate(
            {
                "behavior": {
                    "no_match": "default_profile",
                    "default_profile": "missing",
                },
                "directories": {
                    "input": "/data/input",
                    "output": "/data/output",
                    "temp": "/data/temp",
                },
                "profiles": {
                    "h264_1080p": _sample_profile().model_dump(),
                },
            }
        )


def test_vshift_config_requires_move_dir() -> None:
    with pytest.raises(VShiftException):
        VshiftConfig.model_validate(
            {
                "behavior": {"input_after_success": "move"},
                "directories": {
                    "input": "/data/input",
                    "output": "/data/output",
                    "temp": "/data/temp",
                },
                "profiles": {
                    "h264_1080p": _sample_profile().model_dump(),
                },
            }
        )


def test_vshift_config_rejects_duplicate_rule_ids() -> None:
    with pytest.raises(VShiftException):
        _sample_config(
            rules=[
                {
                    "id": "dup",
                    "match": {"extensions": ["mkv"]},
                    "profile": "h264_1080p",
                },
                {
                    "id": "dup",
                    "match": {"extensions": ["mp4"]},
                    "profile": "h264_720p",
                },
            ]
        )


def test_match_rule_bit_depth_and_hdr() -> None:
    rule = MatchRule.model_validate(
        {
            "id": "4k_hdr",
            "match": {
                "min_height": 2160,
                "min_bit_depth": 10,
                "hdr": True,
            },
            "profile": "4k-10Bit-H265",
        }
    )
    assert rule.matches(
        ProbedInput(
            path=Path("/data/input/movie.mkv"),
            extension="mkv",
            width=3840,
            height=2160,
            bit_depth=10,
            hdr=True,
        )
    )
    assert not rule.matches(
        ProbedInput(
            path=Path("/data/input/movie.mkv"),
            extension="mkv",
            width=3840,
            height=2160,
            bit_depth=10,
            hdr=False,
        )
    )


def test_default_config_loads_h265_profiles() -> None:
    config_path = Path(__file__).parent.parent / "config" / "vshift.yaml"
    config = YamlConfigLoader().load(config_path)

    assert "4k-10Bit-H265" in config.profiles
    assert config.profiles["4k-10Bit-H265"].video.encoder == VideoEncoder.LIBX265
    assert config.profiles["4k-10Bit-H265"].video.bit_depth == 10
    assert config.profiles["1080p-8Bit"].video.height == 1080


def test_example_yaml_loads_into_vshift_config() -> None:
    raw = yaml.safe_load(EXAMPLE_CONFIG_PATH.read_text(encoding="utf-8"))
    config = VshiftConfig.model_validate(raw)

    assert config.version == "1"
    assert config.behavior.no_match == NoMatchAction.IGNORE
    assert config.behavior.max_retries == 3
    assert "h264_1080p" in config.profiles
    assert config.profiles["h264_1080p"].video.encoder == VideoEncoder.AUTO
    assert config.profiles["h264_1080p"].video.quality_mode == QualityMode.CONSTANT
    assert len(config.rules) == 2


def test_video_profile_defaults_encoder_to_auto() -> None:
    profile = _sample_profile()
    assert profile.video.encoder == VideoEncoder.AUTO

import pytest

from benchmark_platform.config import ConfigError
from benchmark_platform.schema import validate_section


def test_missing_required_field_fails() -> None:
    schema = {"frequency_seconds": {"required": True, "type": "positive_int"}}
    with pytest.raises(ConfigError):
        validate_section({}, schema, "observability")


def test_missing_optional_field_is_allowed() -> None:
    schema = {"frequency_seconds": {"required": False, "type": "positive_int"}}
    validate_section({}, schema, "observability")


def test_wrong_type_fails() -> None:
    with pytest.raises(ConfigError):
        validate_section(
            {"frequency_seconds": "fast"},
            {"frequency_seconds": {"required": False, "type": "positive_int"}},
            "observability",
        )


def test_matching_type_passes() -> None:
    validate_section(
        {"frequency_seconds": 15},
        {"frequency_seconds": {"required": False, "type": "positive_int"}},
        "observability",
    )

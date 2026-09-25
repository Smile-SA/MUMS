from __future__ import annotations

import pytest

from benchmark_platform.config import ConfigError
from benchmark_platform.schema import resolve_args, to_cli_args

ENVELOPE = frozenset({"module"})
SCHEMA = {
    "shape": {"type": "string", "default": "day"},
    "minutes": {"type": "positive_int"},
    "needed": {"type": "bool", "required": True},
}


def test_defaults_applied_and_envelope_ignored():
    values = resolve_args(
        {"module": "m", "needed": True}, SCHEMA, "traffic", envelope_keys=ENVELOPE
    )
    assert values == {"shape": "day", "needed": True}


def test_unknown_key_refused():
    with pytest.raises(ConfigError, match="Unknown field"):
        resolve_args({"needed": True, "typo": 1}, SCHEMA, "traffic", envelope_keys=ENVELOPE)


def test_required_missing():
    with pytest.raises(ConfigError, match="Missing required field: 'traffic.needed'"):
        resolve_args({}, SCHEMA, "traffic", envelope_keys=ENVELOPE)


def test_wrong_type():
    with pytest.raises(ConfigError, match="must be of type 'positive_int'"):
        resolve_args({"needed": True, "minutes": 0}, SCHEMA, "traffic", envelope_keys=ENVELOPE)


def test_cli_formatting():
    assert to_cli_args({"a": True, "b": False, "c": 3, "d": {"y": 1, "x": 2}, "e": "s"}) == [
        "--a",
        "true",
        "--b",
        "false",
        "--c",
        "3",
        "--d",
        '{"x": 2, "y": 1}',
        "--e",
        "s",
    ]

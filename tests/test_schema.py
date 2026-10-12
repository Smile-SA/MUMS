from __future__ import annotations

import pytest

from mums.config import ConfigError
from mums.schema import resolve_args, to_cli_args

ENVELOPE = frozenset({"module"})
SCHEMA = {
    "shape": {"type": "string", "description": "default: day (applied by the module)"},
    "minutes": {"type": "positive_int"},
    "needed": {"type": "bool", "required": True},
}


def test_no_default_applied_and_envelope_ignored():
    values = resolve_args(
        {"module": "m", "needed": True}, SCHEMA, "traffic", envelope_keys=ENVELOPE
    )
    assert values == {"needed": True}  # only what the scenario gives


def test_unknown_key_only_warns(capsys):
    values = resolve_args({"needed": True, "typo": 1}, SCHEMA, "traffic", envelope_keys=ENVELOPE)
    assert values == {"needed": True}
    assert "typo" in capsys.readouterr().err


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

from __future__ import annotations

import json
import re
from typing import Any

from benchmark_platform.config import ConfigError

_CHECKERS = {
    "string": lambda v: isinstance(v, str) and v.strip() != "",
    "positive_int": lambda v: isinstance(v, int) and not isinstance(v, bool) and v > 0,
    "bool": lambda v: isinstance(v, bool),
    "mapping": lambda v: isinstance(v, dict),
}

# Named arguments whose value is provided by the runner, not by the scenario.
# A module declares them in `args:` (type: string) only if it wants them, and
# the runner passes them if and only if they are declared.
RUNNER_ARGS = frozenset({"log_dir", "extras_dir"})

_ARG_NAME = re.compile(r"^[a-z][a-z0-9_-]*$")
_SPEC_KEYS = frozenset({"required", "default", "type"})


def arg_schema_problems(schema: Any) -> list[str]:
    """Problems in a module's `args:` declaration (empty list if valid)."""
    if not isinstance(schema, dict):
        return ["'args' must be a mapping."]

    problems: list[str] = []
    for key, spec in schema.items():
        if not isinstance(key, str) or not _ARG_NAME.match(key):
            problems.append(f"invalid argument name {key!r} (lowercase, digits, '_' or '-').")
            continue
        if not isinstance(spec, dict):
            problems.append(f"'{key}' must be a mapping (required/default/type).")
            continue
        unknown = sorted(set(spec) - _SPEC_KEYS)
        if unknown:
            problems.append(f"'{key}' has unknown keys: {', '.join(unknown)}.")
        type_name = spec.get("type")
        if key in RUNNER_ARGS:
            if type_name != "string" or "default" in spec or spec.get("required"):
                problems.append(
                    f"'{key}' is provided by the runner: declare it as {{ type: string }} only."
                )
            continue
        if type_name not in _CHECKERS:
            problems.append(f"'{key}' must declare a type among {', '.join(_CHECKERS)}.")
            continue
        default = spec.get("default")
        if default is not None and not _CHECKERS[type_name](default):
            problems.append(f"default of '{key}' is not of type '{type_name}'.")
    return problems


def resolve_args(
    section: dict[str, Any],
    arg_schema: dict[str, Any],
    name: str,
    *,
    envelope_keys: frozenset[str],
) -> dict[str, Any]:
    """Validate a scenario section against its module's `args:` and return the
    module's arguments with defaults applied. Keys the module does not declare
    are refused (except the runner's own envelope keys, e.g. `type`, `module`)."""
    runner_set = sorted(set(section) & RUNNER_ARGS)
    if runner_set:
        raise ConfigError(
            f"Field(s) {', '.join(runner_set)} in '{name}' are provided by the runner, "
            f"not by the scenario."
        )
    unknown = sorted(set(section) - set(arg_schema) - envelope_keys)
    if unknown:
        raise ConfigError(
            f"Unknown field(s) in '{name}': {', '.join(unknown)} "
            f"(not declared in the module's args)."
        )

    values: dict[str, Any] = {}
    for key, spec in arg_schema.items():
        if key in RUNNER_ARGS:
            continue
        field = f"{name}.{key}"
        if key in section:
            _check_type(section[key], spec["type"], field)
            values[key] = section[key]
        elif spec.get("required"):
            raise ConfigError(f"Missing required field: '{field}'.")
        elif spec.get("default") is not None:
            values[key] = spec["default"]
    return values


def to_cli_args(values: dict[str, Any]) -> list[str]:
    """Named arguments `--<key> <value>`. Booleans become true/false, mappings JSON."""
    args: list[str] = []
    for key, value in values.items():
        args.extend([f"--{key}", _format_value(value)])
    return args


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value)


def _check_type(value: Any, type_name: str, field: str) -> None:
    if not _CHECKERS[type_name](value):
        raise ConfigError(f"Field '{field}' must be of type '{type_name}'.")

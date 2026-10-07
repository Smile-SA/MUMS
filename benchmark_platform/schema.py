from __future__ import annotations

import json
import re
from typing import Any

from benchmark_platform.config import ConfigError
from benchmark_platform.warn import warn, warn_unknown

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
_SPEC_KEYS = frozenset({"required", "type", "description"})


def arg_schema_problems(schema: Any, where: str = "a module's args") -> list[str]:
    """Problems in a module's `args:` declaration (empty list if valid). Unknown
    keys of an argument are ignored with a warning; `default` among them: the
    core applies no default, the module does (and says it in `description`)."""
    if not isinstance(schema, dict):
        return ["'args' must be a mapping."]

    problems: list[str] = []
    for key, spec in schema.items():
        if not isinstance(key, str) or not _ARG_NAME.match(key):
            problems.append(f"invalid argument name {key!r} (lowercase, digits, '_' or '-').")
            continue
        if not isinstance(spec, dict):
            problems.append(f"'{key}' must be a mapping (type, required, description).")
            continue
        if "default" in spec:
            warn(
                f"'default' of argument '{key}' in {where} is ignored: the core applies no "
                "default; the module applies its own (describe it in 'description')."
            )
        warn_unknown(set(spec) - {"default"}, _SPEC_KEYS, f"argument '{key}' of {where}")
        type_name = spec.get("type")
        if key in RUNNER_ARGS:
            if type_name != "string" or spec.get("required"):
                problems.append(f"'{key}' is provided by the runner: declare it as type: string.")
            continue
        if type_name not in _CHECKERS:
            problems.append(f"'{key}' must declare a type among {', '.join(_CHECKERS)}.")
        description = spec.get("description")
        if description is not None and not isinstance(description, str):
            problems.append(f"'description' of '{key}' must be a string.")
    return problems


def resolve_args(
    section: dict[str, Any],
    arg_schema: dict[str, Any],
    name: str,
    *,
    envelope_keys: frozenset[str],
) -> dict[str, Any]:
    """Validate a scenario section against its module's `args:` and return the
    module's arguments: only those given by the scenario (the module applies its
    own defaults). Keys the module does not declare are ignored with a warning
    (except the runner's own envelope keys, e.g. `module`)."""
    runner_set = sorted(set(section) & RUNNER_ARGS)
    if runner_set:
        raise ConfigError(
            f"Field(s) {', '.join(runner_set)} in '{name}' are provided by the runner, "
            f"not by the scenario."
        )
    warn_unknown(
        set(section) - envelope_keys, set(arg_schema), f"'{name}' (not declared by its module)"
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

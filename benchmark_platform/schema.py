from __future__ import annotations

from typing import Any

from benchmark_platform.config import ConfigError

_CHECKERS = {
    "string": lambda v: isinstance(v, str) and v.strip() != "",
    "positive_int": lambda v: isinstance(v, int) and not isinstance(v, bool) and v > 0,
    "bool": lambda v: isinstance(v, bool),
    "mapping": lambda v: isinstance(v, dict),
}


def validate_section(section: dict[str, Any], arg_schema: dict[str, Any], name: str) -> None:
    """Validate a scenario config component section against its module's declared
    ``args:`` schema. Modules own their argument requirements and defaults; the
    core only enforces what the module itself declared."""
    for key, spec in (arg_schema or {}).items():
        if not isinstance(spec, dict):
            continue
        if key not in section:
            if spec.get("required"):
                raise ConfigError(f"Missing required field: '{name}.{key}'.")
            continue
        _check_type(section[key], spec.get("type"), f"{name}.{key}")


def _check_type(value: Any, type_name: str | None, field: str) -> None:
    if type_name is None:
        return
    checker = _CHECKERS.get(type_name)
    if checker is None:
        raise ConfigError(f"Unknown arg type '{type_name}' for field '{field}'.")
    if not checker(value):
        raise ConfigError(f"Field '{field}' must be of type '{type_name}'.")

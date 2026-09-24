from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class ScenarioConfig:
    path: Path
    raw: dict[str, Any]

    @property
    def name(self) -> str:
        return str(self.raw["scenario"]["name"])

    @property
    def seed(self) -> int:
        return int(self.raw["scenario"]["seed"])

    @property
    def duration_seconds(self) -> int:
        return int(self.raw["scenario"]["duration_seconds"])

    @property
    def output_root(self) -> Path:
        return Path(str(self.raw["output"]["root_directory"]))

    @property
    def cleanup_environment(self) -> bool:
        return bool(self.raw["output"].get("cleanup_environment", True))


def _require_mapping(data: Any, field: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ConfigError(f"Field '{field}' must be a mapping.")
    return data


def _require_section(raw: dict[str, Any], section: str) -> dict[str, Any]:
    if section not in raw:
        raise ConfigError(f"Missing required section: '{section}'.")
    return _require_mapping(raw[section], section)


def _optional_section(raw: dict[str, Any], section: str) -> dict[str, Any]:
    if section not in raw:
        return {}
    return _require_mapping(raw[section], section)


def _require_field(section: dict[str, Any], section_name: str, field: str) -> Any:
    if field not in section:
        raise ConfigError(f"Missing required field: '{section_name}.{field}'.")
    return section[field]


def _require_non_empty_string(value: Any, field: str) -> str:
    parsed = str(value).strip()
    if not parsed:
        raise ConfigError(f"Field '{field}' must not be empty.")
    return parsed


def _require_positive_int(value: Any, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"Field '{field}' must be an integer.") from exc
    if parsed <= 0:
        raise ConfigError(f"Field '{field}' must be positive.")
    return parsed


def _validate_component(section: dict[str, Any], section_name: str) -> None:
    # The section name is the module type; `module` points to the module
    # directory, whose module.yaml must declare that type (checked on load).
    _require_non_empty_string(
        _require_field(section, section_name, "module"),
        f"{section_name}.module",
    )


def load_config(path: str | Path) -> ScenarioConfig:
    config_path = Path(path).expanduser().resolve()

    if not config_path.exists():
        raise ConfigError(f"Scenario config does not exist: {config_path}")

    with config_path.open("r", encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)

    raw = _require_mapping(raw, "root")

    version = _require_field(raw, "root", "version")
    if int(version) != 1:
        raise ConfigError(f"Unsupported config version: {version}. Expected version 1.")

    scenario = _require_section(raw, "scenario")
    environment = _require_section(raw, "environment")
    stack = _require_section(raw, "stack")
    observability = _require_section(raw, "observability")
    traffic = _require_section(raw, "traffic")
    optimizer = _require_section(raw, "optimizer")
    output = _require_section(raw, "output")
    post_processing = _optional_section(raw, "post-processing")

    _require_non_empty_string(
        _require_field(scenario, "scenario", "name"),
        "scenario.name",
    )
    _require_positive_int(_require_field(scenario, "scenario", "seed"), "scenario.seed")
    _require_positive_int(
        _require_field(scenario, "scenario", "duration_seconds"),
        "scenario.duration_seconds",
    )

    # Component sections are validated at the framework envelope level only
    # (`module`). Module-specific fields (e.g.
    # environment.workers, observability.frequency_seconds, traffic.shape) are
    # opaque to the core and validated by each module's own `args:` schema in
    # module.yaml — see benchmark_platform.schema.resolve_args.
    _validate_component(environment, "environment")
    _validate_component(stack, "stack")
    _validate_component(observability, "observability")
    _validate_component(traffic, "traffic")
    _validate_component(optimizer, "optimizer")

    if post_processing:
        _validate_component(post_processing, "post-processing")

    _require_non_empty_string(
        _require_field(output, "output", "root_directory"),
        "output.root_directory",
    )

    return ScenarioConfig(path=config_path, raw=raw)

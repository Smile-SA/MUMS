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
    _require_non_empty_string(
        _require_field(section, section_name, "type"),
        f"{section_name}.type",
    )

    if "module" in section:
        _require_non_empty_string(section["module"], f"{section_name}.module")


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
    dataset = _optional_section(raw, "dataset")

    _require_non_empty_string(
        _require_field(scenario, "scenario", "name"),
        "scenario.name",
    )
    _require_positive_int(_require_field(scenario, "scenario", "seed"), "scenario.seed")
    _require_positive_int(
        _require_field(scenario, "scenario", "duration_seconds"),
        "scenario.duration_seconds",
    )

    _validate_component(environment, "environment")
    workers = _require_mapping(
        _require_field(environment, "environment", "workers"),
        "environment.workers",
    )
    _require_positive_int(
        _require_field(workers, "environment.workers", "count"),
        "environment.workers.count",
    )
    _require_non_empty_string(
        _require_field(workers, "environment.workers", "cpu"),
        "environment.workers.cpu",
    )
    _require_non_empty_string(
        _require_field(workers, "environment.workers", "memory"),
        "environment.workers.memory",
    )

    _validate_component(stack, "stack")

    _validate_component(observability, "observability")
    _require_positive_int(
        _require_field(observability, "observability", "frequency_seconds"),
        "observability.frequency_seconds",
    )
    if "local_port" in observability:
        _require_positive_int(observability["local_port"], "observability.local_port")
    if "timeout_seconds" in observability:
        _require_positive_int(observability["timeout_seconds"], "observability.timeout_seconds")

    _validate_component(traffic, "traffic")
    _require_non_empty_string(_require_field(traffic, "traffic", "shape"), "traffic.shape")
    _require_positive_int(
        _require_field(traffic, "traffic", "cycle_minutes"),
        "traffic.cycle_minutes",
    )

    _validate_component(optimizer, "optimizer")

    if dataset:
        _validate_component(dataset, "dataset")
        if "enabled" in dataset and not isinstance(dataset["enabled"], bool):
            raise ConfigError("Field 'dataset.enabled' must be a boolean when provided.")

    _require_non_empty_string(
        _require_field(output, "output", "root_directory"),
        "output.root_directory",
    )

    return ScenarioConfig(path=config_path, raw=raw)

from pathlib import Path

import pytest

from benchmark_platform.config import ConfigError, load_config


def test_basic_config_loads() -> None:
    config = load_config(Path("configs/basic-online-boutique.yaml"))
    assert config.name == "basic-online-boutique"
    assert config.seed == 42
    assert config.duration_seconds > 0


def test_missing_config_fails(tmp_path: Path) -> None:
    missing = tmp_path / "missing.yaml"
    with pytest.raises(ConfigError):
        load_config(missing)


def test_invalid_component_type_fails(tmp_path: Path) -> None:
    config_path = tmp_path / "bad.yaml"
    config_path.write_text(
        '''
version: 1
scenario:
  name: bad
  seed: 1
  duration_seconds: 10
environment:
  type: unsupported
  workers:
    count: 1
    cpu: "1"
    memory: "1Gi"
stack:
  type: online-boutique
observability:
  type: prometheus
  frequency_seconds: 15
traffic:
  type: locust
  shape: journee_type
  cycle_minutes: 60
optimizer:
  type: baseline
output:
  root_directory: output/runs
''',
        encoding="utf-8",
    )

    with pytest.raises(ConfigError):
        load_config(config_path)
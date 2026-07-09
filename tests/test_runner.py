from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from benchmark_platform.config import load_config
from benchmark_platform.runner import run_scenario


def _make_module(
    root: Path, rel_path: str, name: str, module_type: str, actions: list[str]
) -> None:
    d = root / rel_path
    d.mkdir(parents=True)
    lifecycle = "lifecycle:\n" + "".join(f"  {action}: ''\n" for action in actions)
    (d / "module.yaml").write_text(
        f"name: {name}\ntype: {module_type}\nentrypoint: run.sh\n{lifecycle}",
        encoding="utf-8",
    )
    (d / "run.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")


def _make_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    output_dir = tmp_path / "output"

    _make_module(repo, "envs/kind", "envs.kind", "environment", ["create", "destroy"])
    _make_module(repo, "stacks/mystack", "stacks.mystack", "stack", ["deploy"])
    _make_module(repo, "observability/prometheus", "obs.prom", "observability", ["start", "stop"])
    _make_module(repo, "traffic/mytraffic", "traffic.mytraffic", "traffic", ["start", "stop"])
    _make_module(repo, "optimizers/baseline", "opt.baseline", "optimizer", ["deploy"])
    _make_module(repo, "observability/analysis", "obs.analysis", "dataset", ["generate"])

    config_path = repo / "scenario.yaml"
    config_path.write_text(
        f"""\
version: 1
scenario:
  name: dispatch-test
  seed: 99
  duration_seconds: 1
environment:
  type: kind
  module: envs/kind
  workers:
    count: 1
    cpu: "1"
    memory: "1Gi"
stack:
  type: mystack
  module: stacks/mystack
observability:
  type: prometheus
  module: observability/prometheus
  frequency_seconds: 15
traffic:
  type: mytraffic
  module: traffic/mytraffic
  shape: flat
  cycle_minutes: 1
optimizer:
  type: baseline
  module: optimizers/baseline
dataset:
  type: csv
  module: observability/analysis
  enabled: true
output:
  root_directory: {output_dir}
  cleanup_environment: true
""",
        encoding="utf-8",
    )

    return repo, config_path


def test_runner_dispatches_lifecycle_actions_in_order(tmp_path: Path) -> None:
    repo, config_path = _make_repo(tmp_path)
    config = load_config(config_path)

    dispatched: list[tuple[str, str]] = []  # (module_dir, action)
    call_envs: list[dict] = []

    def fake_run_command(command, *, cwd, env=None, log_file=None, check=True):
        module_dir = Path(command[0]).parent.name
        action = command[1]
        dispatched.append((module_dir, action))
        call_envs.append(dict(env or {}))
        return subprocess.CompletedProcess(list(command), 0)

    captured_envs: list[dict] = []

    def fake_capture_stdout(command, *, cwd, env=None, check=True):
        captured_envs.append(dict(env or {}))
        return "/fake/kubeconfig"

    with (
        patch("benchmark_platform.runner.capture_stdout", side_effect=fake_capture_stdout),
        patch("benchmark_platform.runner.run_command", side_effect=fake_run_command),
        patch("benchmark_platform.runner._sleep_with_interrupt"),
        patch("benchmark_platform.runner._collect_kubernetes_state"),
        patch("benchmark_platform.runner._generate_datasets"),
        patch("shutil.copy2"),
    ):
        run_scenario(config, repo_root=repo)

    assert dispatched == [
        ("prometheus", "start"),   # observability.start
        ("mystack", "deploy"),     # stack.deploy
        ("baseline", "deploy"),    # optimizer.deploy
        ("mytraffic", "start"),    # traffic.start
        ("mytraffic", "stop"),     # traffic.stop  (teardown)
        ("prometheus", "stop"),    # observability.stop (teardown)
        ("kind", "destroy"),       # environment.destroy (teardown)
    ]


def test_runner_injects_component_config_env(tmp_path: Path) -> None:
    repo, config_path = _make_repo(tmp_path)
    config = load_config(config_path)

    call_envs: list[dict] = []

    def fake_run_command(command, *, cwd, env=None, log_file=None, check=True):
        call_envs.append(dict(env or {}))
        return subprocess.CompletedProcess(list(command), 0)

    capture_envs: list[dict] = []

    def fake_capture_stdout(command, *, cwd, env=None, check=True):
        capture_envs.append(dict(env or {}))
        return "/fake/kubeconfig"

    with (
        patch("benchmark_platform.runner.capture_stdout", side_effect=fake_capture_stdout),
        patch("benchmark_platform.runner.run_command", side_effect=fake_run_command),
        patch("benchmark_platform.runner._sleep_with_interrupt"),
        patch("benchmark_platform.runner._collect_kubernetes_state"),
        patch("benchmark_platform.runner._generate_datasets"),
        patch("shutil.copy2"),
    ):
        run_scenario(config, repo_root=repo)

    all_envs = capture_envs + call_envs
    for env in all_envs:
        assert "BENCHMARK_COMPONENT_CONFIG" in env, (
            "BENCHMARK_COMPONENT_CONFIG missing from env for a module call"
        )
        parsed = json.loads(env["BENCHMARK_COMPONENT_CONFIG"])
        assert isinstance(parsed, dict)

    # environment section contains workers config
    env_config = json.loads(capture_envs[0]["BENCHMARK_COMPONENT_CONFIG"])
    assert env_config["workers"]["count"] == 1

    # traffic section contains shape
    traffic_env = next(
        e for e in call_envs
        if json.loads(e["BENCHMARK_COMPONENT_CONFIG"]).get("shape") == "flat"
    )
    assert json.loads(traffic_env["BENCHMARK_COMPONENT_CONFIG"])["cycle_minutes"] == 1

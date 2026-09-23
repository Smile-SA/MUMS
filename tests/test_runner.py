from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import yaml

from benchmark_platform.config import load_config
from benchmark_platform.runner import run_scenario


def _make_module(
    root: Path, rel_path: str, name: str, module_type: str, *, lifecycle: str = ""
) -> None:
    d = root / rel_path
    d.mkdir(parents=True)
    (d / "module.yaml").write_text(
        f"name: {name}\ntype: {module_type}\nentrypoint: run.sh\n{lifecycle}", encoding="utf-8"
    )
    (d / "run.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")


def _make_repo(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    repo.mkdir()
    output_dir = tmp_path / "output"

    _make_module(repo, "envs/kind", "envs.kind", "environment")
    _make_module(repo, "stacks/mystack", "stacks.mystack", "stack")
    _make_module(repo, "observability/prometheus", "obs.prom", "observability")
    _make_module(
        repo,
        "traffic/mytraffic",
        "traffic.mytraffic",
        "traffic",
        lifecycle="lifecycle:\n  start: run.sh start\n  stop: run.sh stop\n",
    )
    _make_module(
        repo,
        "optimizers/baseline",
        "opt.baseline",
        "optimizer",
        lifecycle="lifecycle:\n  deploy: run.sh deploy\n",
    )
    _make_module(
        repo,
        "observability/analysis",
        "obs.analysis",
        "post-processing",
        lifecycle="lifecycle:\n  process: run.sh process\n",
    )

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
post-processing:
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

    def fake_run_command(command, *, cwd, env=None, log_file=None, check=True, verbose=False):
        module_dir = Path(command[0]).parent.name
        action = command[1]
        dispatched.append((module_dir, action))
        call_envs.append(dict(env or {}))
        if action == "create" and len(command) > 3:
            Path(command[3]).write_text("/fake/kubeconfig")
        return subprocess.CompletedProcess(list(command), 0)

    with (
        patch("benchmark_platform.runner.run_command", side_effect=fake_run_command),
        patch("benchmark_platform.runner._sleep_with_interrupt"),
        patch("benchmark_platform.runner._collect_kubernetes_state"),
        patch("benchmark_platform.runner.build_provenance", return_value={}),
        patch("benchmark_platform.runner._post_process"),
        patch("shutil.copy2"),
    ):
        run_scenario(config, repo_root=repo)

    assert dispatched == [
        ("kind", "create"),  # environment.create
        ("prometheus", "start"),  # observability.start
        ("mystack", "deploy"),  # stack.deploy
        ("baseline", "deploy"),  # optimizer.deploy
        ("mytraffic", "start"),  # traffic.start
        ("mytraffic", "stop"),  # traffic.stop  (teardown)
        ("prometheus", "stop"),  # observability.stop (teardown)
        ("kind", "destroy"),  # environment.destroy (teardown)
    ]


def test_runner_dispatches_optional_optimizer_start_stop(tmp_path: Path) -> None:
    repo, config_path = _make_repo(tmp_path)

    # optimizers/baseline (declared with only `deploy`) exercises supports("start")
    # is False for a minimal-contract optimizer. Swap in an optimizer module that
    # declares start/stop too, mirroring an online optimizer like optimizers/hots.
    optimizer_dir = repo / "optimizers" / "baseline"
    (optimizer_dir / "module.yaml").write_text(
        "name: opt.online\ntype: optimizer\nentrypoint: run.sh\n"
        "lifecycle:\n  deploy: run.sh deploy\n  start: run.sh start\n  stop: run.sh stop\n",
        encoding="utf-8",
    )

    config = load_config(config_path)

    dispatched: list[tuple[str, str]] = []

    def fake_run_command(command, *, cwd, env=None, log_file=None, check=True, verbose=False):
        module_dir = Path(command[0]).parent.name
        action = command[1]
        dispatched.append((module_dir, action))
        if action == "create" and len(command) > 3:
            Path(command[3]).write_text("/fake/kubeconfig")
        return subprocess.CompletedProcess(list(command), 0)

    with (
        patch("benchmark_platform.runner.run_command", side_effect=fake_run_command),
        patch("benchmark_platform.runner._sleep_with_interrupt"),
        patch("benchmark_platform.runner._collect_kubernetes_state"),
        patch("benchmark_platform.runner.build_provenance", return_value={}),
        patch("benchmark_platform.runner._post_process"),
        patch("shutil.copy2"),
    ):
        run_scenario(config, repo_root=repo)

    assert dispatched == [
        ("kind", "create"),  # environment.create
        ("prometheus", "start"),  # observability.start
        ("mystack", "deploy"),  # stack.deploy
        ("baseline", "deploy"),  # optimizer.deploy
        ("baseline", "start"),  # optimizer.start (declared)
        ("mytraffic", "start"),  # traffic.start
        ("mytraffic", "stop"),  # traffic.stop  (teardown)
        ("baseline", "stop"),  # optimizer.stop (teardown, declared)
        ("prometheus", "stop"),  # observability.stop (teardown)
        ("kind", "destroy"),  # environment.destroy (teardown)
    ]


def test_runner_injects_component_config_env(tmp_path: Path) -> None:
    repo, config_path = _make_repo(tmp_path)
    config = load_config(config_path)

    call_envs: list[dict] = []

    def fake_run_command(command, *, cwd, env=None, log_file=None, check=True, verbose=False):
        call_envs.append(dict(env or {}))
        if command[1] == "create" and len(command) > 3:
            Path(command[3]).write_text("/fake/kubeconfig")
        return subprocess.CompletedProcess(list(command), 0)

    with (
        patch("benchmark_platform.runner.run_command", side_effect=fake_run_command),
        patch("benchmark_platform.runner._sleep_with_interrupt"),
        patch("benchmark_platform.runner._collect_kubernetes_state"),
        patch("benchmark_platform.runner.build_provenance", return_value={}),
        patch("benchmark_platform.runner._post_process"),
        patch("shutil.copy2"),
    ):
        run_scenario(config, repo_root=repo)

    for env in call_envs:
        assert "BENCHMARK_COMPONENT_CONFIG" in env, (
            "BENCHMARK_COMPONENT_CONFIG missing from env for a module call"
        )
        parsed = json.loads(env["BENCHMARK_COMPONENT_CONFIG"])
        assert isinstance(parsed, dict)

    # environment section contains workers config
    env_config = json.loads(call_envs[0]["BENCHMARK_COMPONENT_CONFIG"])
    assert env_config["workers"]["count"] == 1

    # traffic section contains shape
    traffic_env = next(
        e for e in call_envs if json.loads(e["BENCHMARK_COMPONENT_CONFIG"]).get("shape") == "flat"
    )
    assert json.loads(traffic_env["BENCHMARK_COMPONENT_CONFIG"])["cycle_minutes"] == 1


def test_runner_writes_provenance_to_manifest(tmp_path: Path) -> None:
    repo, config_path = _make_repo(tmp_path)
    config = load_config(config_path)

    def fake_run_command(command, *, cwd, env=None, log_file=None, check=True, verbose=False):
        if command[1] == "create" and len(command) > 3:
            Path(command[3]).write_text("/fake/kubeconfig")
        return subprocess.CompletedProcess(list(command), 0)

    fake_provenance = {"tool_versions": {"kubectl": "v1.99.0"}, "notes": []}

    with (
        patch("benchmark_platform.runner.run_command", side_effect=fake_run_command),
        patch("benchmark_platform.runner._sleep_with_interrupt"),
        patch("benchmark_platform.runner._collect_kubernetes_state"),
        patch(
            "benchmark_platform.runner.build_provenance", return_value=fake_provenance
        ) as mock_bp,
        patch("benchmark_platform.runner._post_process"),
        patch("shutil.copy2"),
    ):
        run_dir = run_scenario(config, repo_root=repo)
        mock_bp.assert_called_once()
        assert mock_bp.call_args.kwargs["kubeconfig"] == "/fake/kubeconfig"
        assert mock_bp.call_args.kwargs["artifacts_dir"] == run_dir / "artifacts"
        assert mock_bp.call_args.kwargs["cleanup_environment"] is True

    manifest = yaml.safe_load((run_dir / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["provenance"] == fake_provenance


def test_runner_records_provenance_error_without_failing_run(tmp_path: Path) -> None:
    repo, config_path = _make_repo(tmp_path)
    config = load_config(config_path)

    def fake_run_command(command, *, cwd, env=None, log_file=None, check=True, verbose=False):
        if command[1] == "create" and len(command) > 3:
            Path(command[3]).write_text("/fake/kubeconfig")
        return subprocess.CompletedProcess(list(command), 0)

    with (
        patch("benchmark_platform.runner.run_command", side_effect=fake_run_command),
        patch("benchmark_platform.runner._sleep_with_interrupt"),
        patch("benchmark_platform.runner._collect_kubernetes_state"),
        patch("benchmark_platform.runner.build_provenance", side_effect=RuntimeError("boom")),
        patch("benchmark_platform.runner._post_process"),
        patch("shutil.copy2"),
    ):
        run_dir = run_scenario(config, repo_root=repo)

    manifest = yaml.safe_load((run_dir / "manifest.yaml").read_text(encoding="utf-8"))
    assert manifest["status"] == "completed"
    assert "boom" in manifest["provenance"]["error"]

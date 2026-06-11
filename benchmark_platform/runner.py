from __future__ import annotations

import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from benchmark_platform.config import ScenarioConfig
from benchmark_platform.shell import capture_stdout, run_command


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _safe_name(value: str) -> str:
    allowed = []
    for char in value.lower():
        if char.isalnum() or char in {"-", "_"}:
            allowed.append(char)
        elif char.isspace():
            allowed.append("-")
    return "".join(allowed).strip("-") or "scenario"


def build_run_id(config: ScenarioConfig) -> str:
    return f"{_safe_name(config.name)}-{_utc_timestamp()}-seed{config.seed}"


def _write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        yaml.safe_dump(data, stream, sort_keys=False)


def run_scenario(config: ScenarioConfig, *, repo_root: Path) -> Path:
    run_id = build_run_id(config)
    run_dir = config.output_root / run_id
    logs_dir = run_dir / "logs"
    metrics_dir = run_dir / "metrics"

    run_dir.mkdir(parents=True, exist_ok=False)
    logs_dir.mkdir(parents=True, exist_ok=True)
    metrics_dir.mkdir(parents=True, exist_ok=True)

    copied_config = run_dir / "config.yaml"
    shutil.copy2(config.path, copied_config)

    manifest: dict[str, Any] = {
        "run_id": run_id,
        "scenario": config.name,
        "seed": config.seed,
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "config": str(copied_config),
        "artifacts": {
            "logs": str(logs_dir),
            "metrics": str(metrics_dir / "metrics.om"),
        },
    }
    _write_yaml(run_dir / "manifest.yaml", manifest)

    raw = config.raw
    env_cfg = raw["environment"]
    workers = env_cfg["workers"]
    observability = raw["observability"]
    traffic = raw["traffic"]
    optimizer = raw["optimizer"]

    kubeconfig_path: str | None = None
    environment_created = False
    observability_started = False
    traffic_started = False

    env_vars = {
        "KIND_NODE_IMAGE": str(env_cfg.get("node_image", "kindest/node:v1.34.0")),
        "METALLB_IP_RANGE": str(env_cfg.get("metallb", {}).get("ip_range", "auto")),
    }

    try:
        workers_arg = f"count={workers['count']},cpu={workers['cpu']},memory={workers['memory']}"

        kubeconfig_path = capture_stdout(
            ["./envs/kind.sh", "create", str(config.seed), f"--workers={workers_arg}"],
            cwd=repo_root,
            env=env_vars,
        )
        environment_created = True

        manifest["environment"] = {
            "type": "kind",
            "kubeconfig": kubeconfig_path,
            "node_image": env_vars["KIND_NODE_IMAGE"],
        }
        _write_yaml(run_dir / "manifest.yaml", manifest)

        run_command(
            [
                "./observability/prometheus/run.sh",
                "start",
                kubeconfig_path,
                str(metrics_dir),
                f"--frequency={observability['frequency_seconds']}",
            ],
            cwd=repo_root,
            log_file=logs_dir / "observability.log",
        )
        observability_started = True

        run_command(
            ["./stacks/online-boutique/deploy.sh", kubeconfig_path, str(config.seed)],
            cwd=repo_root,
            log_file=logs_dir / "stack.log",
        )

        run_command(
            ["./optimizers/baseline/run.sh", "start"],
            cwd=repo_root,
            log_file=logs_dir / "optimizer.log",
        )
        manifest["optimizer"] = {"type": str(optimizer["type"])}

        run_command(
            [
                "./traffic/online-boutique/run.sh",
                "start",
                kubeconfig_path,
                str(config.seed),
                f"--shape={traffic['shape']}",
                f"--duration={traffic['cycle_minutes']}",
            ],
            cwd=repo_root,
            log_file=logs_dir / "traffic-start.log",
        )
        traffic_started = True

        time.sleep(config.duration_seconds)

        manifest["status"] = "completed"
        return run_dir

    except BaseException as exc:
        manifest["status"] = "failed"
        manifest["error"] = str(exc)
        raise

    finally:
        if kubeconfig_path:
            if traffic_started:
                run_command(
                    ["./traffic/online-boutique/run.sh", "stop", kubeconfig_path],
                    cwd=repo_root,
                    log_file=logs_dir / "traffic-stop.log",
                    check=False,
                )

            if observability_started:
                run_command(
                    ["./observability/prometheus/run.sh", "stop", kubeconfig_path],
                    cwd=repo_root,
                    log_file=logs_dir / "observability-stop.log",
                    check=False,
                )

            if environment_created and config.cleanup_environment:
                run_command(
                    ["./envs/kind.sh", "destroy", str(config.seed)],
                    cwd=repo_root,
                    log_file=logs_dir / "environment-destroy.log",
                    check=False,
                )

        manifest["ended_at"] = datetime.now(timezone.utc).isoformat()
        _write_yaml(run_dir / "manifest.yaml", manifest)

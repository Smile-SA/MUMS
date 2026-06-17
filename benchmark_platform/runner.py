from __future__ import annotations

import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from benchmark_platform.config import ScenarioConfig
from benchmark_platform.manifest import RunManifest, utc_now_iso
from benchmark_platform.paths import RunPaths
from benchmark_platform.shell import capture_stdout, run_command


class RunnerInterrupted(RuntimeError):
    pass


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


def _collect_kubernetes_state(kubeconfig: str, paths: RunPaths, repo_root: Path) -> None:
    commands = {
        "nodes.yaml": ["kubectl", "--kubeconfig", kubeconfig, "get", "nodes", "-o", "yaml"],
        "pods.yaml": ["kubectl", "--kubeconfig", kubeconfig, "get", "pods", "-A", "-o", "yaml"],
        "services.yaml": ["kubectl", "--kubeconfig", kubeconfig, "get", "svc", "-A", "-o", "yaml"],
        "deployments.yaml": [
            "kubectl",
            "--kubeconfig",
            kubeconfig,
            "get",
            "deployments",
            "-A",
            "-o",
            "yaml",
        ],
        "events.txt": [
            "kubectl",
            "--kubeconfig",
            kubeconfig,
            "get",
            "events",
            "-A",
            "--sort-by=.lastTimestamp",
        ],
    }

    for filename, command in commands.items():
        output_path = paths.kubernetes / filename
        with output_path.open("w", encoding="utf-8") as stream:
            subprocess.run(
                command,
                cwd=str(repo_root),
                text=True,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
            )


def _sleep_with_interrupt(duration_seconds: int) -> None:
    end = time.monotonic() + duration_seconds
    while time.monotonic() < end:
        time.sleep(min(1.0, end - time.monotonic()))


def run_scenario(config: ScenarioConfig, *, repo_root: Path) -> Path:
    run_id = build_run_id(config)
    paths = RunPaths.create(config.output_root / run_id)

    shutil.copy2(config.path, paths.config)

    manifest = RunManifest(
        paths.manifest,
        {
            "run_id": run_id,
            "scenario": config.name,
            "seed": config.seed,
            "status": "running",
            "started_at": utc_now_iso(),
            "config": str(paths.config),
            "artifacts": {
                "logs": str(paths.logs),
                "runtime": str(paths.runtime),
                "metrics": str(paths.metrics),
                "traffic": str(paths.traffic),
                "kubernetes": str(paths.kubernetes),
                "datasets": str(paths.datasets),
            },
        },
    )

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
        "BENCHMARK_RUN_DIR": str(paths.root),
        "BENCHMARK_LOG_DIR": str(paths.logs),
        "BENCHMARK_PID_DIR": str(paths.pids),
        "BENCHMARK_TRAFFIC_DIR": str(paths.traffic),
        "BENCHMARK_METRICS_DIR": str(paths.metrics),
    }

    try:
        workers_arg = f"count={workers['count']},cpu={workers['cpu']},memory={workers['memory']}"

        manifest.append_event({"time": utc_now_iso(), "type": "environment.create.start"})
        kubeconfig_path = capture_stdout(
            ["./envs/kind.sh", "create", str(config.seed), f"--workers={workers_arg}"],
            cwd=repo_root,
            env=env_vars,
        )
        environment_created = True

        kubeconfig_copy = paths.runtime / "kubeconfig"
        shutil.copy2(kubeconfig_path, kubeconfig_copy)

        manifest.set(
            "environment",
            {
                "type": "kind",
                "kubeconfig": str(kubeconfig_copy),
                "original_kubeconfig": kubeconfig_path,
                "node_image": env_vars["KIND_NODE_IMAGE"],
            },
        )
        manifest.append_event({"time": utc_now_iso(), "type": "environment.create.complete"})

        manifest.append_event({"time": utc_now_iso(), "type": "observability.start"})
        run_command(
            [
                "./observability/prometheus/run.sh",
                "start",
                kubeconfig_path,
                str(paths.metrics),
                f"--frequency={observability['frequency_seconds']}",
            ],
            cwd=repo_root,
            env=env_vars,
            log_file=paths.logs / "observability-start.log",
        )
        observability_started = True

        manifest.append_event({"time": utc_now_iso(), "type": "stack.deploy.start"})
        run_command(
            ["./stacks/online-boutique/deploy.sh", kubeconfig_path, str(config.seed)],
            cwd=repo_root,
            env=env_vars,
            log_file=paths.logs / "stack.log",
        )
        manifest.append_event({"time": utc_now_iso(), "type": "stack.deploy.complete"})

        manifest.set("optimizer", {"type": str(optimizer["type"])})
        run_command(
            ["./optimizers/baseline/run.sh", "start"],
            cwd=repo_root,
            env=env_vars,
            log_file=paths.logs / "optimizer.log",
        )

        manifest.append_event({"time": utc_now_iso(), "type": "traffic.start"})
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
            env=env_vars,
            log_file=paths.logs / "traffic-start.log",
        )
        traffic_started = True

        _sleep_with_interrupt(config.duration_seconds)

        manifest.update(status="completed")
        return paths.root

    except KeyboardInterrupt as exc:
        manifest.update(status="interrupted", error="Interrupted by user")
        raise RunnerInterrupted("Benchmark run interrupted by user.") from exc

    except BaseException as exc:
        manifest.update(status="failed", error=str(exc))
        raise

    finally:
        if kubeconfig_path:
            if traffic_started:
                manifest.append_event({"time": utc_now_iso(), "type": "traffic.stop"})
                run_command(
                    ["./traffic/online-boutique/run.sh", "stop", kubeconfig_path],
                    cwd=repo_root,
                    env=env_vars,
                    log_file=paths.logs / "traffic-stop.log",
                    check=False,
                )

            if observability_started:
                manifest.append_event({"time": utc_now_iso(), "type": "observability.stop"})
                run_command(
                    ["./observability/prometheus/run.sh", "stop", kubeconfig_path],
                    cwd=repo_root,
                    env=env_vars,
                    log_file=paths.logs / "observability-stop.log",
                    check=False,
                )

            manifest.append_event({"time": utc_now_iso(), "type": "kubernetes.collect-state"})
            _collect_kubernetes_state(kubeconfig_path, paths, repo_root)

            if environment_created and config.cleanup_environment:
                manifest.append_event({"time": utc_now_iso(), "type": "environment.destroy"})
                run_command(
                    ["./envs/kind.sh", "destroy", str(config.seed)],
                    cwd=repo_root,
                    env=env_vars,
                    log_file=paths.logs / "environment-destroy.log",
                    check=False,
                )

        manifest.update(ended_at=utc_now_iso())

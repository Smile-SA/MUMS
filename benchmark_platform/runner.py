from __future__ import annotations

import json
import shutil
import subprocess
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from benchmark_platform.config import ScenarioConfig
from benchmark_platform.manifest import RunManifest, utc_now_iso
from benchmark_platform.modules import ModuleSpec, load_module
from benchmark_platform.paths import RunPaths
from benchmark_platform.provenance import build_provenance
from benchmark_platform.schema import validate_section
from benchmark_platform.shell import run_command


class RunnerInterrupted(RuntimeError):
    pass


def _utc_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


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


def _component_module_path(
    raw: dict[str, object],
    section: str,
    default: str,
) -> str:
    section_data = raw.get(section, {})
    if isinstance(section_data, dict):
        value = section_data.get("module")
        if value:
            return str(value)
    return default


def _load_and_validate(
    repo_root: Path,
    raw: dict[str, object],
    section: str,
    default: str,
    expected_type: str,
) -> ModuleSpec:
    module = load_module(
        repo_root,
        _component_module_path(raw, section, default),
        expected_type=expected_type,
    )
    validate_section(raw.get(section, {}), module.arg_schema, section)
    return module


def _collect_kubernetes_state(
    kubeconfig: str,
    paths: RunPaths,
    repo_root: Path,
) -> None:
    commands = {
        "nodes.yaml": [
            "kubectl",
            "--kubeconfig",
            kubeconfig,
            "get",
            "nodes",
            "-o",
            "yaml",
        ],
        "pods.yaml": [
            "kubectl",
            "--kubeconfig",
            kubeconfig,
            "get",
            "pods",
            "-A",
            "-o",
            "yaml",
        ],
        "services.yaml": [
            "kubectl",
            "--kubeconfig",
            kubeconfig,
            "get",
            "svc",
            "-A",
            "-o",
            "yaml",
        ],
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


def _print_step(
    component: str,
    action: str,
    status: str,
    *,
    verbose: bool = False,
) -> None:
    if verbose:
        print(
            f"[{component}]{' ' * (16 - len(component))}{action:<10} {status}",
            flush=True,
        )
    else:
        print(
            f"\r\033[K[{component}]{' ' * (16 - len(component))}{action:<10} {status}",
            end="",
            flush=True,
        )


def _run_step(
    component: str,
    action: str,
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    log_file: Path | None = None,
    verbose: bool = False,
    quiet: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:

    if not quiet:
        _print_step(component, action, "...", verbose=verbose)

    try:
        result = run_command(
            command,
            cwd=cwd,
            env=env,
            log_file=log_file,
            check=check,
            verbose=verbose,
        )

        if not quiet:
            _print_step(component, action, "✓", verbose=verbose)
            print()

        return result

    except BaseException:
        if not quiet:
            _print_step(component, action, "ERROR", verbose=verbose)
            print()

        raise


def _post_process(
    paths: RunPaths,
    repo_root: Path,
    env_vars: dict[str, str],
    manifest: RunManifest,
    post_processing_module: ModuleSpec | None,
    post_processing_section: dict,
    *,
    verbose: bool,
    quiet: bool,
) -> None:
    if post_processing_module is None:
        manifest.set(
            "post-processing_generation",
            {
                "status": "skipped",
                "reason": "module disabled",
            },
        )
        return

    manifest.append_event(
        {
            "time": utc_now_iso(),
            "type": "post-processing.process.start",
        }
    )

    command = post_processing_module.command(
        "process",
        str(paths.root)
    )

    result = _run_step(
        component="post-processing",
        action="process",
        command=command,
        cwd=repo_root,
        env=_component_env(
            env_vars,
            post_processing_section,
            paths.module_artifacts(post_processing_module.name),
        ),
        log_file=paths.logs / "post-processing.log",
        check=False,
        verbose=verbose,
        quiet=quiet,
    )

    status = "completed" if result.returncode == 0 else "failed"

    manifest.set(
        "post-processing_generation",
        {
            "status": status,
            "returncode": result.returncode,
        },
    )
    manifest.append_event(
        {
            "time": utc_now_iso(),
            "type": f"post-processing.process.{status}",
        }
    )


def _sleep_with_interrupt(duration_seconds: int) -> None:
    end = time.monotonic() + duration_seconds

    while time.monotonic() < end:
        time.sleep(min(1.0, end - time.monotonic()))


def _component_env(
    base: dict[str, str],
    section: dict,
    artifact_dir: Path | None = None,
) -> dict[str, str]:
    env = {
        **base,
        "BENCHMARK_COMPONENT_CONFIG": json.dumps(section),
    }

    if artifact_dir is not None:
        env["BENCHMARK_ARTIFACT_DIR"] = str(artifact_dir)

    return env


def run_scenario(
    config: ScenarioConfig,
    *,
    repo_root: Path,
    verbose: bool = False,
    quiet: bool = False,
) -> Path:
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
                "post-processing": str(paths.post_processing),
                "artifacts": str(paths.artifacts),
            },
        },
    )

    raw = config.raw

    env_cfg = raw["environment"]
    observability = raw["observability"]
    traffic = raw["traffic"]
    optimizer = raw["optimizer"]
    post_processing = raw.get("post-processing", {})

    environment_module = _load_and_validate(
        repo_root,
        raw,
        "environment",
        "envs/kind",
        "environment",
    )

    stack_module = _load_and_validate(
        repo_root,
        raw,
        "stack",
        "stacks/online-boutique",
        "stack",
    )

    observability_module = _load_and_validate(
        repo_root,
        raw,
        "observability",
        "observability/prometheus",
        "observability",
    )

    traffic_module = _load_and_validate(
        repo_root,
        raw,
        "traffic",
        "traffic/online-boutique",
        "traffic",
    )

    optimizer_module = _load_and_validate(
        repo_root,
        raw,
        "optimizer",
        "optimizers/baseline",
        "optimizer",
    )

    post_processing_enabled = True

    if isinstance(post_processing, dict) and "enabled" in post_processing:
        post_processing_enabled = bool(post_processing["enabled"])

    post_processing_module = (
        _load_and_validate(
            repo_root,
            raw,
            "post-processing",
            "observability/analysis",
            "post-processing",
        )
        if post_processing_enabled
        else None
    )

    manifest.set(
        "modules",
        {
            "environment": environment_module.as_manifest_record(),
            "stack": stack_module.as_manifest_record(),
            "observability": observability_module.as_manifest_record(),
            "traffic": traffic_module.as_manifest_record(),
            "optimizer": optimizer_module.as_manifest_record(),
            "post-processing": (
                post_processing_module.as_manifest_record()
                if post_processing_module
                else None
            ),
        },
    )

    kubeconfig_path: str | None = None
    environment_created = False
    observability_started = False
    traffic_started = False
    environment_result_file = paths.runtime / f".environment-result-{config.seed}"
    optimizer_started = False

    env_vars = {
        "BENCHMARK_RUN_DIR": str(paths.root),
        "BENCHMARK_LOG_DIR": str(paths.logs),
        "BENCHMARK_PID_DIR": str(paths.pids),
        "BENCHMARK_TRAFFIC_DIR": str(paths.traffic),
        "BENCHMARK_METRICS_DIR": str(paths.metrics),
    }

    try:
        # Environment
        manifest.append_event(
            {
                "time": utc_now_iso(),
                "type": "environment.create.start",
            }
        )

        _run_step(
            component="env",
            action="create",
            command=environment_module.command(
                "create",
                str(config.seed),
                str(environment_result_file),
            ),
            cwd=repo_root,
            env=_component_env(
                env_vars,
                env_cfg,
                paths.module_artifacts(environment_module.name),
            ),
            log_file=paths.logs / "environment-create.log",
            verbose=verbose,
            quiet=quiet,
        )

        if not environment_result_file.is_file():
            raise RuntimeError("Environment create did not produce a result file.")

        kubeconfig_path = environment_result_file.read_text(encoding="utf-8").strip()
        environment_result_file.unlink()

        if not kubeconfig_path:
            raise RuntimeError("Environment create produced an empty result file.")
        environment_created = True

        kubeconfig_copy = paths.runtime / "kubeconfig"
        shutil.copy2(kubeconfig_path, kubeconfig_copy)

        manifest.set(
            "environment",
            {
                "type": "kind",
                "kubeconfig": str(kubeconfig_copy),
                "original_kubeconfig": kubeconfig_path,
            },
        )

        manifest.append_event(
            {
                "time": utc_now_iso(),
                "type": "environment.create.complete",
            }
        )

        # Observability
        manifest.append_event(
            {
                "time": utc_now_iso(),
                "type": "observability.start",
            }
        )

        _run_step(
            component="observability",
            action="start",
            command=observability_module.command(
                "start",
                kubeconfig_path,
                str(paths.metrics),
            ),
            cwd=repo_root,
            env=_component_env(
                env_vars,
                observability,
                paths.module_artifacts(observability_module.name),
            ),
            log_file=paths.logs / "observability-start.log",
            verbose=verbose,
            quiet=quiet,
        )

        observability_started = True

        # Stack
        manifest.append_event(
            {
                "time": utc_now_iso(),
                "type": "stack.deploy.start",
            }
        )

        _run_step(
            component="stack",
            action="deploy",
            command=stack_module.command(
                "deploy",
                kubeconfig_path,
                str(config.seed),
            ),
            cwd=repo_root,
            env=_component_env(
                env_vars,
                raw["stack"],
                paths.module_artifacts(stack_module.name),
            ),
            log_file=paths.logs / "stack.log",
            verbose=verbose,
            quiet=quiet,
        )

        manifest.append_event(
            {
                "time": utc_now_iso(),
                "type": "stack.deploy.complete",
            }
        )

        # Optimizer
        manifest.set(
            "optimizer",
            {
                "type": str(optimizer["type"]),
            },
        )

        _run_step(
            component="optimizer",
            action="deploy",
            command=optimizer_module.command(
                "deploy",
                kubeconfig_path,
            ),
            cwd=repo_root,
            env=_component_env(
                env_vars,
                optimizer,
                paths.module_artifacts(optimizer_module.name),
            ),
            log_file=paths.logs / "optimizer.log",
            verbose=verbose,
            quiet=quiet,
        )

        if optimizer_module.supports("start"):
            _run_step(
                component="optimizer",
                action="start",
                command=optimizer_module.command("start", kubeconfig_path),
                cwd=repo_root,
                env=_component_env(
                    env_vars,
                    optimizer,
                    paths.module_artifacts(optimizer_module.name),
                ),
                log_file=paths.logs / "optimizer-start.log",
                verbose=verbose,
                quiet=quiet,
            )
            optimizer_started = True

        # Traffic
        manifest.append_event(
            {
                "time": utc_now_iso(),
                "type": "traffic.start",
            }
        )

        _run_step(
            component="traffic",
            action="start",
            command=traffic_module.command(
                "start",
                kubeconfig_path,
                str(config.seed),
            ),
            cwd=repo_root,
            env=_component_env(
                env_vars,
                traffic,
                paths.module_artifacts(traffic_module.name),
            ),
            log_file=paths.logs / "traffic-start.log",
            verbose=verbose,
            quiet=quiet,
        )

        traffic_started = True

        if not quiet:
            _print_step("run", "wait", "...", verbose=verbose)

        _sleep_with_interrupt(config.duration_seconds)

        if not quiet:
            _print_step("run", "wait", "✓", verbose=verbose)
            print()

        manifest.update(status="completed")
        return paths.root

    except KeyboardInterrupt as exc:
        manifest.update(
            status="interrupted",
            error="Interrupted by user",
        )
        raise RunnerInterrupted("Benchmark run interrupted by user.") from exc

    except BaseException as exc:
        manifest.update(
            status="failed",
            error=str(exc),
        )
        raise

    finally:
        if kubeconfig_path:
            # Traffic cleanup
            if traffic_started and traffic_module.supports("stop"):
                manifest.append_event(
                    {
                        "time": utc_now_iso(),
                        "type": "traffic.stop",
                    }
                )

                _run_step(
                    component="traffic",
                    action="stop",
                    command=traffic_module.command(
                        "stop",
                        kubeconfig_path,
                    ),
                    cwd=repo_root,
                    env=_component_env(
                        env_vars,
                        traffic,
                        paths.module_artifacts(traffic_module.name),
                    ),
                    log_file=paths.logs / "traffic-stop.log",
                    check=False,
                    verbose=verbose,
                    quiet=quiet,
                )

            if optimizer_started and optimizer_module.supports("stop"):
                manifest.append_event({"time": utc_now_iso(), "type": "optimizer.stop"})
                _run_step(
                    component="optimizer",
                    action="stop",
                    command=optimizer_module.command("stop", kubeconfig_path),
                    cwd=repo_root,
                    env=_component_env(
                        env_vars,
                        optimizer,
                        paths.module_artifacts(optimizer_module.name),
                    ),
                    log_file=paths.logs / "optimizer-stop.log",
                    check=False,
                    verbose=verbose,
                    quiet=quiet,
                )

            # Observability cleanup
            if observability_started:
                manifest.append_event(
                    {
                        "time": utc_now_iso(),
                        "type": "observability.stop",
                    }
                )

                _run_step(
                    component="observability",
                    action="stop",
                    command=observability_module.command(
                        "stop",
                        kubeconfig_path,
                    ),
                    cwd=repo_root,
                    env=_component_env(
                        env_vars,
                        observability,
                        paths.module_artifacts(observability_module.name),
                    ),
                    log_file=paths.logs / "observability-stop.log",
                    check=False,
                    verbose=verbose,
                    quiet=quiet,
                )

            # Kubernetes state collection is internal runner bookkeeping,
            # so it is deliberately not displayed in the progress dashboard.
            manifest.append_event(
                {
                    "time": utc_now_iso(),
                    "type": "kubernetes.collect-state",
                }
            )

            _collect_kubernetes_state(
                kubeconfig_path,
                paths,
                repo_root,
            )

            manifest.append_event({"time": utc_now_iso(), "type": "provenance.collect"})
            try:
                provenance = build_provenance(
                    pods_yaml_path=paths.kubernetes / "pods.yaml",
                    kubeconfig=kubeconfig_path,
                    artifacts_dir=paths.artifacts,
                    cleanup_environment=config.cleanup_environment,
                )
                manifest.set("provenance", provenance)
            except Exception as exc:  # provenance capture must never fail the run
                manifest.set("provenance", {"error": str(exc)})

            # Dataset generation
            _post_process(
                paths,
                repo_root,
                env_vars,
                manifest,
                post_processing_module,
                post_processing,
                verbose=verbose,
                quiet=quiet,
            )

            # Environment cleanup
            if environment_created and config.cleanup_environment:
                manifest.append_event(
                    {
                        "time": utc_now_iso(),
                        "type": "environment.destroy",
                    }
                )

                _run_step(
                    component="env",
                    action="destroy",
                    command=environment_module.command(
                        "destroy",
                        str(config.seed),
                    ),
                    cwd=repo_root,
                    env=_component_env(
                        env_vars,
                        env_cfg,
                        paths.module_artifacts(environment_module.name),
                    ),
                    log_file=paths.logs / "environment-destroy.log",
                    check=False,
                    verbose=verbose,
                    quiet=quiet,
                )

        manifest.update(ended_at=utc_now_iso())

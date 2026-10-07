"""Registry of live environments, and cleanup of the ones left behind.

The runner registers an environment *before* creating it and unregisters it
once its `destroy` has succeeded. An environment is therefore left in the
registry when its destroy never completed: the run was killed, the machine
went to sleep, the destroy failed, or `cleanup_environment` was false.

One directory per environment, `<id>/entry.yaml`. The entry is complete
before `create` starts and is removed only after `destroy` succeeds, so an
unreadable entry can only come from an interrupted registration or removal:
in both cases the environment does not exist, and the entry is simply
deleted, without calling `destroy`.

The registry lives outside run outputs, in a per-user state directory
(`$XDG_STATE_HOME/benchmark-platform/environments/`, by default
`~/.local/state/benchmark-platform/environments/`), so deleting run outputs
never loses track of an environment. Each entry holds what is needed to call
the environment module's own `destroy <id>`: the core knows nothing about what
an environment is made of.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from benchmark_platform.dependencies import UTILS_PATH_ENV
from benchmark_platform.manifest import utc_now_iso
from benchmark_platform.modules import ModuleSpec, load_module_at
from benchmark_platform.shell import run_command


def default_state_dir() -> Path:
    base = os.environ.get("XDG_STATE_HOME") or str(Path.home() / ".local" / "state")
    return Path(base) / "benchmark-platform"


@dataclass(frozen=True)
class RegisteredEnvironment:
    environment_id: str
    module_path: Path
    options: tuple[str, ...]
    run_dir: Path | None
    utils_path: Path | None
    registered_at: str
    entry_dir: Path


class EnvironmentRegistry:
    def __init__(self, state_dir: Path | None = None) -> None:
        self.root = (state_dir or default_state_dir()) / "environments"

    def _entry_dir(self, environment_id: str) -> Path:
        return self.root / environment_id

    def register(
        self,
        environment_id: str,
        module: ModuleSpec,
        options: tuple[str, ...],
        run_dir: Path,
        utils_path: Path,
    ) -> None:
        entry_dir = self._entry_dir(environment_id)
        entry_dir.mkdir(parents=True, exist_ok=True)
        entry = {
            "environment_id": environment_id,
            "module_path": str(module.module_path),
            "options": list(options),
            "run_dir": str(run_dir),
            "utils_path": str(utils_path),
            "registered_at": utc_now_iso(),
        }
        (entry_dir / "entry.yaml").write_text(
            yaml.safe_dump(entry, sort_keys=False), encoding="utf-8"
        )

    def unregister(self, environment_id: str) -> None:
        shutil.rmtree(self._entry_dir(environment_id), ignore_errors=True)

    def entries(self) -> list[RegisteredEnvironment]:
        return self.scan()[0]

    def scan(self) -> tuple[list[RegisteredEnvironment], list[Path]]:
        """(valid entries, directories of unreadable entries)."""
        if not self.root.is_dir():
            return [], []
        found = []
        broken: list[Path] = []
        for entry_dir in sorted(p for p in self.root.iterdir() if p.is_dir()):
            entry_file = entry_dir / "entry.yaml"
            try:
                data: Any = yaml.safe_load(entry_file.read_text(encoding="utf-8"))
            except (OSError, yaml.YAMLError):
                broken.append(entry_dir)
                continue
            if (
                not isinstance(data, dict)
                or not data.get("environment_id")
                or not data.get("module_path")
            ):
                broken.append(entry_dir)
                continue
            found.append(
                RegisteredEnvironment(
                    environment_id=str(data["environment_id"]),
                    module_path=Path(str(data["module_path"])),
                    options=tuple(str(o) for o in data.get("options") or []),
                    run_dir=Path(str(data["run_dir"])) if data.get("run_dir") else None,
                    utils_path=Path(str(data["utils_path"])) if data.get("utils_path") else None,
                    registered_at=str(data.get("registered_at", "")),
                    entry_dir=entry_file.parent,
                )
            )
        return found, broken


def clean_environments(
    *,
    registry: EnvironmentRegistry,
    environment_id: str | None = None,
    verbose: bool = False,
) -> tuple[list[str], list[str]]:
    """Call `destroy <id>` for every registered environment (or only
    `environment_id`). Returns (destroyed ids, errors)."""
    destroyed: list[str] = []
    errors: list[str] = []

    entries, broken = registry.scan()
    for entry_dir in broken:
        # Interrupted registration or removal: the environment does not exist.
        if environment_id is None or entry_dir.name == environment_id:
            print(f"=== Removing incomplete registry entry: {entry_dir.name} ===")
            shutil.rmtree(entry_dir, ignore_errors=True)

    for entry in entries:
        if environment_id and entry.environment_id != environment_id:
            continue
        try:
            module = load_module_at(entry.module_path, expected_type="environment")
            # Runner-provided arguments: the run's own directories if they still
            # exist, otherwise directories inside the registry entry.
            runner_values: dict[str, Path] = {}
            if "log_dir" in module.arg_schema:
                runner_values["log_dir"] = entry.entry_dir / "logs"
            if "extras_dir" in module.arg_schema:
                run_extras = entry.run_dir / "extras" / module.name if entry.run_dir else None
                runner_values["extras_dir"] = (
                    run_extras if run_extras and run_extras.is_dir() else entry.entry_dir / "extras"
                )
            for path in runner_values.values():
                path.mkdir(parents=True, exist_ok=True)
            runner_options: list[str] = []
            for key, path in runner_values.items():
                runner_options.extend([f"--{key}", str(path)])

            command = module.command(
                "destroy", (entry.environment_id,), options=(*runner_options, *entry.options)
            )
            print(f"=== Destroying environment {entry.environment_id} ({module.name}) ===")
            result = run_command(
                command,
                cwd=module.module_path,
                env={UTILS_PATH_ENV: str(entry.utils_path)} if entry.utils_path else None,
                log_file=entry.entry_dir / "destroy.log",
                check=False,
                verbose=verbose,
            )
            if result.returncode == 0:
                registry.unregister(entry.environment_id)
                destroyed.append(entry.environment_id)
            else:
                log_file = entry.entry_dir / "destroy.log"
                errors.append(f"{entry.environment_id}: destroy failed (log: {log_file})")
        except Exception as exc:  # one broken entry must not stop the others
            errors.append(f"{entry.environment_id}: {exc}")

    return destroyed, errors

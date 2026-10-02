"""Module dependencies: installation and verification.

A module declares its dependencies in `module.yaml`, a util in `util.yaml`:

    dependencies:
      entrypoint: dependencies.sh   # optional: the module's dependency script
      commands: [kubectl, helm]     # must be on PATH
      utils: [utils.helm]           # utils, by name

The dependency script takes a single argument:

- `install`: installs whatever the module needs (system packages, Python
  packages with `python3 -m pip`, downloads...). Must succeed when run again on
  an already installed system.
- `check`: verifies what `commands` cannot express (a running service, a
  downloaded file, a Python package...). Run before every benchmark: fast and
  without side effects.

The core walks a module and its utils recursively (utils first, each once).
Installation runs every `install`, then the full check, so a failed
installation shows up immediately. The script runs from the module directory,
in the caller's environment unchanged (the same as the modules' actions: the
core does not assume any virtual environment), plus BENCHMARK_UTILS_PATH.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from benchmark_platform.discovery import UTILS_PATH_ENV, DiscoveryError, ModuleIndex

DEPENDENCY_KEYS = frozenset({"entrypoint", "commands", "utils"})
_CHECK_TIMEOUT_SECONDS = 60


class DependencyError(RuntimeError):
    pass


def dependency_problems(dependencies: Any) -> list[str]:
    """Problems in a `dependencies:` declaration (empty list if valid)."""
    if dependencies is None:
        return []
    if not isinstance(dependencies, dict):
        return ["'dependencies' must be a mapping."]
    problems: list[str] = []
    unknown = sorted(set(dependencies) - DEPENDENCY_KEYS)
    if unknown:
        problems.append(
            f"unknown key(s): {', '.join(unknown)} (allowed: {', '.join(sorted(DEPENDENCY_KEYS))})."
        )
    entrypoint = dependencies.get("entrypoint")
    if entrypoint is not None and (not isinstance(entrypoint, str) or not entrypoint.strip()):
        problems.append("'entrypoint' must be a non-empty string.")
    for key in ("commands", "utils"):
        value = dependencies.get(key)
        if value is None:
            continue
        if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
            problems.append(f"'{key}' must be a list of non-empty strings.")
    return problems


@dataclass(frozen=True)
class Node:
    name: str
    path: Path
    script: Path | None
    commands: tuple[str, ...]


def _read_dependencies(path: Path) -> dict[str, Any]:
    descriptor = path / "module.yaml" if (path / "module.yaml").is_file() else path / "util.yaml"
    data = yaml.safe_load(descriptor.read_text(encoding="utf-8")) or {}
    dependencies = data.get("dependencies") if isinstance(data, dict) else None
    problems = dependency_problems(dependencies)
    if problems:
        raise DependencyError(
            f"Invalid dependencies in {descriptor}: " + " ".join(problems)
        )
    return dependencies or {}


def resolve(index: ModuleIndex, names: list[str]) -> list[Node]:
    """The given modules and all their dependencies, dependencies first."""
    ordered: list[Node] = []
    done: set[str] = set()
    in_progress: set[str] = set()

    def visit(name: str, required_by: str | None) -> None:
        if name in done:
            return
        if name in in_progress:
            raise DependencyError(f"Circular dependency involving '{name}'.")
        try:
            path = index.path(name)
        except DiscoveryError as exc:
            origin = f" (required by '{required_by}')" if required_by else ""
            raise DependencyError(f"{exc}{origin}") from exc
        in_progress.add(name)
        dependencies = _read_dependencies(path)
        for dependency in [
            *(dependencies.get("utils") or []),
            *(dependencies.get("modules") or []),
        ]:
            visit(dependency, name)
        script = dependencies.get("entrypoint")
        ordered.append(
            Node(
                name=name,
                path=path,
                script=path / script if script else None,
                commands=tuple(dependencies.get("commands") or []),
            )
        )
        in_progress.discard(name)
        done.add(name)

    for name in names:
        visit(name, None)
    return ordered


def _script_env(utils_path: Path) -> dict[str, str]:
    # Same environment as the modules' actions (the caller's, unchanged), plus
    # BENCHMARK_UTILS_PATH: a check sees exactly what an action will see.
    env = os.environ.copy()
    env[UTILS_PATH_ENV] = str(utils_path)
    return env


def _run_script(
    node: Node, mode: str, utils_path: Path, *, capture: bool
) -> subprocess.CompletedProcess[str]:
    assert node.script is not None
    return subprocess.run(
        [str(node.script), mode],
        cwd=str(node.path),
        env=_script_env(utils_path),
        text=True,
        capture_output=capture,
        timeout=_CHECK_TIMEOUT_SECONDS if mode == "check" else None,
        check=False,
    )


def node_problems(node: Node, utils_path: Path) -> list[str]:
    """What is missing for one module or util alone (its utils not included)."""
    problems: list[str] = []
    for command in node.commands:
        if shutil.which(command) is None:
            problems.append(f"command not found: {command}")
    if node.script is None:
        return problems
    if not node.script.is_file():
        problems.append(f"dependency script not found: {node.script}")
        return problems
    try:
        result = _run_script(node, "check", utils_path, capture=True)
        if result.returncode != 0:
            output = (result.stdout + result.stderr).strip().splitlines()[-5:]
            detail = f": {' / '.join(output)}" if output else ""
            problems.append(f"check failed{detail}")
    except subprocess.TimeoutExpired:
        problems.append(f"check timed out ({_CHECK_TIMEOUT_SECONDS}s)")
    except OSError as exc:
        problems.append(f"check could not run: {exc}")
    return problems


def check_dependencies(index: ModuleIndex, names: list[str], utils_path: Path) -> None:
    """Check `commands` and run every `check`, for the given modules and their
    utils. Raises DependencyError listing everything that is missing."""
    missing: dict[str, list[str]] = {}
    for node in resolve(index, names):
        problems = node_problems(node, utils_path)
        if problems:
            missing[node.name] = problems

    if missing:
        lines = ["Missing dependencies:"]
        for name, problems in missing.items():
            lines.append(f"  {name}:")
            lines.extend(f"    - {problem}" for problem in problems)
            lines.append(f"    install: benchmark-platform deps install {name}")
        raise DependencyError("\n".join(lines))


def install_dependencies(index: ModuleIndex, names: list[str], utils_path: Path) -> None:
    """Run every `install` (dependencies first), then the full check."""
    for node in resolve(index, names):
        if node.script is None:
            continue
        if not node.script.is_file():
            raise DependencyError(f"{node.name}: dependency script not found: {node.script}")
        print(f"=== Installing dependencies: {node.name} ===", flush=True)
        try:
            result = _run_script(node, "install", utils_path, capture=False)
        except OSError as exc:
            raise DependencyError(f"{node.name}: install could not run: {exc}") from exc
        if result.returncode != 0:
            raise DependencyError(f"{node.name}: install failed (exit code {result.returncode}).")
    check_dependencies(index, names, utils_path)

"""Pre-run dependency check.

A module declares its dependencies in `module.yaml`:

    dependencies:
      commands: [kubectl, locust]      # must be on PATH
      checks: ["docker info"]          # shell commands that must succeed (e.g. a service is up)
      utils: [utils/helm]              # checked recursively
      modules: [observability/prometheus]
      python: [requirements.txt]       # installed by `make setup-module`, not checked here

The runner checks every module of a scenario, recursively, before creating
anything, and refuses to start if something is missing.
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEPENDENCY_KEYS = frozenset({"commands", "checks", "utils", "modules", "python"})
_CHECK_TIMEOUT_SECONDS = 30


class DependencyError(RuntimeError):
    pass


def dependency_problems(dependencies: Any) -> list[str]:
    """Problems in a module's `dependencies:` declaration (empty list if valid)."""
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
    for key, value in dependencies.items():
        if value is None:
            continue
        if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
            problems.append(f"'{key}' must be a list of non-empty strings.")
    return problems


@dataclass
class _Report:
    missing: dict[str, list[str]] = field(default_factory=dict)
    visited: set[Path] = field(default_factory=set)

    def add(self, module: str, problem: str) -> None:
        self.missing.setdefault(module, []).append(problem)


def _resolve(repo_root: Path, module_path: str) -> Path:
    path = Path(module_path).expanduser()
    if not path.is_absolute():
        path = repo_root / path
    return path.resolve()


def _display(repo_root: Path, path: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return str(path)


def _check(repo_root: Path, path: Path, report: _Report) -> None:
    if path in report.visited:
        return
    report.visited.add(path)
    name = _display(repo_root, path)

    descriptor_path = path / "module.yaml"
    if not descriptor_path.is_file():
        report.add(name, f"module.yaml not found in {path}")
        return
    descriptor = yaml.safe_load(descriptor_path.read_text(encoding="utf-8")) or {}
    dependencies = descriptor.get("dependencies") if isinstance(descriptor, dict) else None
    problems = dependency_problems(dependencies)
    if problems:
        for problem in problems:
            report.add(name, f"invalid dependencies: {problem}")
        return
    dependencies = dependencies or {}

    for command in dependencies.get("commands") or []:
        if shutil.which(command) is None:
            report.add(name, f"command not found: {command}")

    for check in dependencies.get("checks") or []:
        try:
            result = subprocess.run(
                check,
                shell=True,
                cwd=str(path),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=_CHECK_TIMEOUT_SECONDS,
                check=False,
            )
            ok = result.returncode == 0
        except subprocess.TimeoutExpired:
            ok = False
        if not ok:
            report.add(name, f"check failed: {check}")

    for dependency in [*(dependencies.get("utils") or []), *(dependencies.get("modules") or [])]:
        dependency_path = _resolve(repo_root, dependency)
        if not dependency_path.is_dir():
            report.add(name, f"dependency not found: {dependency}")
            continue
        _check(repo_root, dependency_path, report)


def check_dependencies(repo_root: Path, module_paths: list[Path]) -> None:
    """Check the dependencies of the given modules, recursively. Raises
    DependencyError listing everything that is missing, with the install command."""
    repo_root = repo_root.resolve()
    report = _Report()
    for path in module_paths:
        _check(repo_root, path.resolve(), report)

    if report.missing:
        lines = ["Missing dependencies, the run cannot start:"]
        for module, problems in report.missing.items():
            lines.append(f"  {module}:")
            lines.extend(f"    - {problem}" for problem in problems)
            lines.append(f"    install: make setup-module MODULE={module}")
        raise DependencyError("\n".join(lines))

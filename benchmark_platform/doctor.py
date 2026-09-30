"""`benchmark-platform doctor`: an informative overview of the machine and of
the platform, for when things go wrong. It checks nothing on behalf of other
commands (they do their own checks) and knows no module in particular."""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

from benchmark_platform.cleanup import EnvironmentRegistry
from benchmark_platform.dependencies import DependencyError, node_problems, resolve
from benchmark_platform.discovery import MODULE_PATHS_ENV, DiscoveryError, discover
from benchmark_platform.runner import CORE_COMMANDS, utils_path

OK = "[OK]  "
KO = "[KO]  "
INFO = "      "

# Python packages the core imports (see pyproject.toml).
_CORE_PACKAGES = ("yaml",)


def _output(command: list[str]) -> str | None:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None
    text = (result.stdout or result.stderr).strip()
    return text.splitlines()[0] if result.returncode == 0 and text else None


def _section(title: str) -> None:
    print(f"\n=== {title} ===")


def run_doctor(repo_root: Path) -> None:
    repo_root = repo_root.resolve()

    _section("Python")
    print(f"{INFO}interpreter: {sys.executable} ({sys.version.split()[0]})")
    if sys.prefix != sys.base_prefix:
        print(f"{INFO}virtual environment: {sys.prefix}")
    else:
        print(f"{INFO}virtual environment: none (system or user interpreter)")
    for package in _CORE_PACKAGES:
        try:
            importlib.import_module(package)
            print(f"{OK}package {package}")
        except ImportError:
            print(f"{KO}package {package} missing (reinstall the platform)")

    _section("Core prerequisites")
    for command in CORE_COMMANDS:
        path = shutil.which(command)
        if path is None:
            print(f"{KO}{command}: not found (install it manually)")
        else:
            version = _output([command, "version", "--client"]) or ""
            print(f"{OK}{command}: {path} {version}".rstrip())

    _section("Repository")
    print(f"{INFO}root: {repo_root}")
    branch = _output(["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"])
    commit = _output(["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"])
    if branch and commit:
        dirty = _output(["git", "-C", str(repo_root), "status", "--porcelain"])
        state = "uncommitted changes" if dirty else "clean"
        print(f"{INFO}git: {branch} @ {commit} ({state})")
    else:
        print(f"{INFO}git: not a git working tree")
    print(f"{INFO}{MODULE_PATHS_ENV}: {os.environ.get(MODULE_PATHS_ENV) or '(not set)'}")

    _section("Modules and utils (dependencies)")
    try:
        index = discover(repo_root)
        nodes = resolve(index, sorted(index.modules))
    except (DiscoveryError, DependencyError) as exc:
        print(f"{KO}{exc}")
    else:
        for node in sorted(nodes, key=lambda n: n.name):
            problems = node_problems(node, utils_path(repo_root))
            if problems:
                print(f"{KO}{node.name}: {'; '.join(problems)}")
            else:
                print(f"{OK}{node.name}")

    _section("Registered environments")
    entries, broken = EnvironmentRegistry().scan()
    if not entries and not broken:
        print(f"{INFO}none")
    for entry in entries:
        print(
            f"{INFO}{entry.environment_id} (registered {entry.registered_at}, run {entry.run_dir})"
        )
    for entry_dir in broken:
        print(f"{INFO}{entry_dir.name} (incomplete entry, removed by the next clean)")

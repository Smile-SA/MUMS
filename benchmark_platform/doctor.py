"""`benchmark-platform doctor`: an informative overview of the machine and of
the platform, for when things go wrong. It checks nothing on behalf of other
commands (they do their own checks) and knows no module in particular."""

from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
from pathlib import Path

from benchmark_platform import settings
from benchmark_platform.cleanup import EnvironmentRegistry
from benchmark_platform.dependencies import DependencyError, node_problems, resolve
from benchmark_platform.discovery import DiscoveryError, discover
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


def run_doctor() -> None:
    # The platform's own code (for its git state), not where modules are.
    repo_root = Path(__file__).resolve().parent.parent

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
    print(f"{INFO}platform: {repo_root}")
    print(f"{INFO}configuration file: {settings.config_file()}")
    for key in settings.VARIABLES:
        try:
            setting = settings.describe(key)
        except settings.SettingsError as exc:
            print(f"{KO}{exc}")
            break
        value = setting.value
        shown = ", ".join(value) if isinstance(value, list) else value
        missing = KO if value is None and key != "env" else INFO
        print(f"{missing}{key}: {shown or 'not set'} ({setting.source})")
    branch = _output(["git", "-C", str(repo_root), "rev-parse", "--abbrev-ref", "HEAD"])
    commit = _output(["git", "-C", str(repo_root), "rev-parse", "--short", "HEAD"])
    if branch and commit:
        dirty = _output(["git", "-C", str(repo_root), "status", "--porcelain"])
        state = "uncommitted changes" if dirty else "clean"
        print(f"{INFO}git: {branch} @ {commit} ({state})")
    else:
        print(f"{INFO}git: not a git working tree")

    _section("Modules and utils (dependencies)")
    try:
        index = discover()
        nodes = resolve(index, [*sorted(index.modules), *sorted(index.utils)])
    except (DiscoveryError, DependencyError) as exc:
        print(f"{KO}{exc}")
    else:
        for node in sorted(nodes, key=lambda n: n.name):
            problems = node_problems(node, utils_path())
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

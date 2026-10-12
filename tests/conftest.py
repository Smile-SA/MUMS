"""Fake modules for core tests: the core is tested against modules of its own,
never against the platform's real modules."""

from __future__ import annotations

import os
import stat
import textwrap
from pathlib import Path

import pytest
import yaml

SIGNATURES = {
    "environment": {"create": "<seed> <id> <output_file>", "destroy": "<id>"},
    "stack": {"deploy": "<kubeconfig> <seed>", "delete": "<kubeconfig>"},
    "observability": {"start": "<kubeconfig> <data_dir>", "stop": "<kubeconfig>"},
    "traffic": {"start": "<kubeconfig> <seed> <data_dir>", "stop": "<kubeconfig>"},
    "optimizer": {"start": "<kubeconfig>", "stop": "<kubeconfig>"},
    "disruption": {"start": "<kubeconfig> <seed>", "stop": "<kubeconfig>"},
    "post-processing": {"run": "<data_dir>"},
}

# Records every call in $CALLS_LOG. `create` writes a kubeconfig path to its
# output file. FAIL_<ACTION>=1 in a module's directory makes that action fail.
SCRIPT = textwrap.dedent(
    """\
    #!/usr/bin/env bash
    set -eu
    here="$(cd "$(dirname "$0")" && pwd)"
    echo "$(basename "$here") $*" >> "$CALLS_LOG"
    [ -f "$here/FAIL_$1" ] && exit 3
    if [ "$1" = create ]; then echo "$FAKE_KUBECONFIG" > "$4"; fi
    exit 0
    """
)


def make_module(root: Path, name: str, module_type: str, **overrides) -> Path:
    path = root / name
    path.mkdir(parents=True)
    descriptor = {
        "name": name,
        "type": module_type,
        "contract": 1,
        "entrypoint": "run.sh",
        "lifecycle": dict(SIGNATURES[module_type]),
        "args": {},
    }
    descriptor.update(overrides)
    (path / "module.yaml").write_text(yaml.safe_dump(descriptor), encoding="utf-8")
    script = path / "run.sh"
    script.write_text(SCRIPT, encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return path


@pytest.fixture
def platform(tmp_path, monkeypatch):
    """A repo root with one fake module per type, a fake kubectl, and a scenario."""
    root = tmp_path / "repo"
    modules = root / "mods"
    for module_type in SIGNATURES:
        make_module(modules, module_type, module_type)

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    kubectl = bin_dir / "kubectl"
    kubectl.write_text("#!/bin/sh\necho fake\n", encoding="utf-8")
    kubectl.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    # Where modules and utils are: set at installation, here for the test repo.
    (root / "utils").mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("MUMS_MODULE_PATHS", str(root))
    monkeypatch.setenv("MUMS_UTILS_PATH", str(root / "utils"))

    kubeconfig = tmp_path / "kubeconfig"
    kubeconfig.write_text("fake", encoding="utf-8")
    calls = tmp_path / "calls.log"
    monkeypatch.setenv("CALLS_LOG", str(calls))
    monkeypatch.setenv("FAKE_KUBECONFIG", str(kubeconfig))

    scenario = {
        "version": 1,
        "scenario": {"name": "Test scénario", "seed": 42, "duration_seconds": 1},
        **{module_type: {"module": module_type} for module_type in SIGNATURES},
        "output": {"root_directory": str(tmp_path / "runs")},
    }

    class Platform:
        pass

    p = Platform()
    p.root, p.modules, p.calls, p.scenario = root, modules, calls, scenario

    def write_scenario(data=None) -> Path:
        path = tmp_path / "scenario.yaml"
        path.write_text(yaml.safe_dump(data or p.scenario), encoding="utf-8")
        return path

    def read_calls() -> list[str]:
        if not calls.exists():
            return []
        return [" ".join(line.split()[:2]) for line in calls.read_text().splitlines()]

    p.write_scenario, p.read_calls = write_scenario, read_calls
    return p


@pytest.fixture(autouse=True)
def _isolated_config(tmp_path, monkeypatch):
    """Never read the configuration file of the installation running the tests."""
    monkeypatch.setenv("MUMS_CONFIG", str(tmp_path / "mums.yaml"))

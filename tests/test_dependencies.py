from __future__ import annotations

import stat

import pytest
import yaml

from benchmark_platform.dependencies import (
    DependencyError,
    check_dependencies,
    install_dependencies,
    resolve,
)
from benchmark_platform.discovery import DiscoveryError, discover


def _util(root, name, dependencies=None, script=None):
    path = root / name
    path.mkdir(parents=True)
    descriptor = {"name": name}
    if dependencies is not None:
        descriptor["dependencies"] = dependencies
    (path / "module.yaml").write_text(yaml.safe_dump(descriptor))
    if script is not None:
        file = path / "deps.sh"
        file.write_text(script)
        file.chmod(file.stat().st_mode | stat.S_IEXEC)
    return path


SCRIPT = """#!/bin/sh
case "$1" in
  install) touch installed ;;
  check) [ -f installed ] || { echo "not installed"; exit 1; } ;;
esac
"""


def test_discovery_by_name(tmp_path):
    _util(tmp_path, "a")
    _util(tmp_path / "nested", "b")
    index = discover(tmp_path)
    assert set(index.modules) == {"a", "b"}
    with pytest.raises(DiscoveryError, match="Unknown module 'c'"):
        index.path("c")


def test_discovery_extra_roots_and_duplicates(tmp_path, monkeypatch):
    _util(tmp_path / "repo", "a")
    _util(tmp_path / "ext", "b")
    monkeypatch.setenv("BENCHMARK_MODULE_PATHS", str(tmp_path / "ext"))
    assert set(discover(tmp_path / "repo").modules) == {"a", "b"}
    _util(tmp_path / "ext2", "a")
    monkeypatch.setenv("BENCHMARK_MODULE_PATHS", str(tmp_path / "ext2"))
    with pytest.raises(DiscoveryError, match="Two modules are named 'a'"):
        discover(tmp_path / "repo")


def test_resolve_dependencies_first(tmp_path):
    _util(tmp_path, "base")
    _util(tmp_path, "mid", {"utils": ["base"]})
    _util(tmp_path, "top", {"utils": ["mid", "base"]})
    order = [n.name for n in resolve(discover(tmp_path), ["top"])]
    assert order == ["base", "mid", "top"]


def test_cycle_detected(tmp_path):
    _util(tmp_path, "a", {"utils": ["b"]})
    _util(tmp_path, "b", {"utils": ["a"]})
    with pytest.raises(DependencyError, match="Circular"):
        resolve(discover(tmp_path), ["a"])


def test_check_reports_everything(tmp_path):
    _util(tmp_path, "u", {"commands": ["nope-util"]})
    _util(
        tmp_path,
        "m",
        {"commands": ["nope-cmd", "sh"], "utils": ["u"], "entrypoint": "deps.sh"},
        script=SCRIPT,
    )
    with pytest.raises(DependencyError) as exc:
        check_dependencies(discover(tmp_path), ["m"], tmp_path)
    message = str(exc.value)
    assert "command not found: nope-cmd" in message
    assert "command not found: nope-util" in message
    assert "check failed: not installed" in message
    assert "benchmark-platform deps install m" in message


def test_install_then_check(tmp_path):
    _util(tmp_path, "m", {"entrypoint": "deps.sh"}, script=SCRIPT)
    install_dependencies(discover(tmp_path), ["m"], tmp_path)
    assert (tmp_path / "m" / "installed").exists()
    check_dependencies(discover(tmp_path), ["m"], tmp_path)


def test_install_that_does_not_satisfy_check_fails(tmp_path):
    _util(
        tmp_path,
        "m",
        {"entrypoint": "deps.sh"},
        script='#!/bin/sh\n[ "$1" = check ] && exit 1\nexit 0\n',
    )
    with pytest.raises(DependencyError, match="check failed"):
        install_dependencies(discover(tmp_path), ["m"], tmp_path)


def test_unknown_dependency(tmp_path):
    _util(tmp_path, "m", {"utils": ["ghost"]})
    with pytest.raises(DependencyError, match="Unknown module 'ghost'.*required by 'm'"):
        check_dependencies(discover(tmp_path), ["m"], tmp_path)


def test_script_gets_utils_path(tmp_path):
    script = '#!/bin/sh\n[ "$BENCHMARK_UTILS_PATH" = "%s" ]\n' % (tmp_path / "u")
    _util(tmp_path, "m", {"entrypoint": "deps.sh"}, script=script)
    check_dependencies(discover(tmp_path), ["m"], tmp_path / "u")

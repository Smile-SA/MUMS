from __future__ import annotations

import os
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


@pytest.fixture(autouse=True)
def _paths(tmp_path, monkeypatch):
    """By default: modules in tmp_path, utils in tmp_path/utils."""
    (tmp_path / "utils").mkdir(exist_ok=True)
    monkeypatch.setenv("BENCHMARK_MODULE_PATHS", str(tmp_path))
    monkeypatch.setenv("BENCHMARK_UTILS_PATH", str(tmp_path / "utils"))


SCRIPT = """#!/bin/sh
case "$1" in
  install) touch installed ;;
  check) [ -f installed ] || { echo "not installed"; exit 1; } ;;
esac
"""


def test_discovery_by_name(tmp_path):
    _util(tmp_path, "a")
    _util(tmp_path / "nested", "b")
    index = discover()
    assert set(index.modules) == {"a", "b"}
    with pytest.raises(DiscoveryError, match="Unknown module or util 'c'"):
        index.path("c")


def test_discovery_several_roots_and_duplicates(tmp_path, monkeypatch):
    _util(tmp_path / "repo", "a")
    _util(tmp_path / "ext", "b")
    roots = [tmp_path / "repo", tmp_path / "ext"]
    monkeypatch.setenv("BENCHMARK_MODULE_PATHS", os.pathsep.join(map(str, roots)))
    assert set(discover().modules) == {"a", "b"}
    _util(tmp_path / "ext2", "a")
    roots.append(tmp_path / "ext2")
    monkeypatch.setenv("BENCHMARK_MODULE_PATHS", os.pathsep.join(map(str, roots)))
    with pytest.raises(DiscoveryError, match="Two are named 'a'"):
        discover()


@pytest.mark.parametrize("variable", ["BENCHMARK_MODULE_PATHS", "BENCHMARK_UTILS_PATH"])
def test_variables_required(monkeypatch, variable):
    monkeypatch.delenv(variable)
    with pytest.raises(DiscoveryError, match="is not set"):
        discover()


def test_resolve_dependencies_first(tmp_path):
    _util(tmp_path, "base")
    _util(tmp_path, "mid", {"utils": ["base"]})
    _util(tmp_path, "top", {"utils": ["mid", "base"]})
    order = [n.name for n in resolve(discover(), ["top"])]
    assert order == ["base", "mid", "top"]


def test_cycle_detected(tmp_path):
    _util(tmp_path, "a", {"utils": ["b"]})
    _util(tmp_path, "b", {"utils": ["a"]})
    with pytest.raises(DependencyError, match="Circular"):
        resolve(discover(), ["a"])


def test_check_reports_everything(tmp_path):
    _util(tmp_path, "u", {"commands": ["nope-util"]})
    _util(
        tmp_path,
        "m",
        {"commands": ["nope-cmd", "sh"], "utils": ["u"], "entrypoint": "deps.sh"},
        script=SCRIPT,
    )
    with pytest.raises(DependencyError) as exc:
        check_dependencies(discover(), ["m"], tmp_path)
    message = str(exc.value)
    assert "command not found: nope-cmd" in message
    assert "command not found: nope-util" in message
    assert "check failed: not installed" in message
    assert "benchmark-platform deps install m" in message


def test_install_then_check(tmp_path):
    _util(tmp_path, "m", {"entrypoint": "deps.sh"}, script=SCRIPT)
    install_dependencies(discover(), ["m"], tmp_path)
    assert (tmp_path / "m" / "installed").exists()
    check_dependencies(discover(), ["m"], tmp_path)


def test_install_that_does_not_satisfy_check_fails(tmp_path):
    _util(
        tmp_path,
        "m",
        {"entrypoint": "deps.sh"},
        script='#!/bin/sh\n[ "$1" = check ] && exit 1\nexit 0\n',
    )
    with pytest.raises(DependencyError, match="check failed"):
        install_dependencies(discover(), ["m"], tmp_path)


def test_unknown_dependency(tmp_path):
    _util(tmp_path, "m", {"utils": ["ghost"]})
    with pytest.raises(DependencyError, match="Unknown module or util 'ghost'.*required by 'm'"):
        check_dependencies(discover(), ["m"], tmp_path)


def test_script_gets_utils_path(tmp_path):
    script = '#!/bin/sh\n[ "$BENCHMARK_UTILS_PATH" = "%s" ]\n' % (tmp_path / "u")
    _util(tmp_path, "m", {"entrypoint": "deps.sh"}, script=script)
    check_dependencies(discover(), ["m"], tmp_path / "u")


def test_doctor_reports_each_module(tmp_path, capsys, monkeypatch):
    from benchmark_platform.doctor import run_doctor

    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    _util(tmp_path, "good", {"commands": ["sh"]})
    _util(tmp_path, "bad", {"commands": ["nope-cmd"]})
    run_doctor()
    out = capsys.readouterr().out
    assert "[OK]  good" in out
    assert "[KO]  bad: command not found: nope-cmd" in out


def _real_util(repo, name, dependencies=None):
    path = repo / "utils" / name.removeprefix("utils.")
    path.mkdir(parents=True)
    descriptor = {"name": name}
    if dependencies is not None:
        descriptor["dependencies"] = dependencies
    (path / "util.yaml").write_text(yaml.safe_dump(descriptor))
    return path


def test_utils_found_only_in_utils_directory(tmp_path):
    _real_util(tmp_path, "helm")
    stray = tmp_path / "ext" / "stray"
    stray.mkdir(parents=True)
    (stray / "util.yaml").write_text(yaml.safe_dump({"name": "utils.stray"}))
    index = discover()
    assert set(index.utils) == {"helm"}  # a util.yaml elsewhere is ignored
    assert index.path("helm") == tmp_path / "utils" / "helm"


def test_module_depends_on_util(tmp_path):
    _real_util(tmp_path, "base", {"commands": ["sh"]})
    _util(tmp_path / "mods", "m", {"utils": ["base"]})
    order = [n.name for n in resolve(discover(), ["m"])]
    assert order == ["base", "m"]

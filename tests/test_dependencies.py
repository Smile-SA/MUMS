from __future__ import annotations

import pytest

from benchmark_platform.dependencies import DependencyError, check_dependencies
from tests.conftest import make_module


def test_all_present(tmp_path):
    path = make_module(
        tmp_path, "t", "traffic", dependencies={"commands": ["sh"], "checks": ["true"]}
    )
    check_dependencies(tmp_path, [path])


def test_missing_reported_recursively(tmp_path):
    util = tmp_path / "utils" / "u"
    util.mkdir(parents=True)
    (util / "module.yaml").write_text("dependencies:\n  commands: [nope-util]\n")
    path = make_module(
        tmp_path,
        "t",
        "traffic",
        dependencies={"commands": ["nope-cmd"], "checks": ["false"], "utils": ["utils/u"]},
    )
    with pytest.raises(DependencyError) as exc:
        check_dependencies(tmp_path, [path])
    message = str(exc.value)
    assert "command not found: nope-cmd" in message
    assert "check failed: false" in message
    assert "command not found: nope-util" in message
    assert "make setup-module MODULE=t" in message


def test_missing_dependency_directory(tmp_path):
    path = make_module(tmp_path, "t", "traffic", dependencies={"utils": ["utils/absent"]})
    with pytest.raises(DependencyError, match="dependency not found: utils/absent"):
        check_dependencies(tmp_path, [path])

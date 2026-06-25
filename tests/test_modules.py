from pathlib import Path

import pytest

from benchmark_platform.modules import ModuleError, load_module


def test_load_existing_module() -> None:
    module = load_module(Path(".").resolve(), "traffic/online-boutique", expected_type="traffic")

    assert module.name == "traffic.online-boutique"
    assert module.type == "traffic"
    assert module.command("start", "kubeconfig", "42")[0] == "./traffic/online-boutique/run.sh"


def test_wrong_module_type_fails() -> None:
    with pytest.raises(ModuleError):
        load_module(Path(".").resolve(), "traffic/online-boutique", expected_type="environment")


def test_missing_module_fails() -> None:
    with pytest.raises(ModuleError):
        load_module(Path(".").resolve(), "does/not/exist")

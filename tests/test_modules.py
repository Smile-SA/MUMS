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


def test_missing_lifecycle_raises(tmp_path: Path) -> None:
    module_dir = tmp_path / "traffic" / "notype"
    module_dir.mkdir(parents=True)
    (module_dir / "module.yaml").write_text(
        "name: traffic.notype\ntype: traffic\nentrypoint: run.sh\n", encoding="utf-8"
    )
    (module_dir / "run.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    module = load_module(tmp_path, "traffic/notype", expected_type="traffic")

    with pytest.raises(ModuleError):
        module.supports("stop")


def test_supports_reflects_declared_lifecycle(tmp_path: Path) -> None:
    module_dir = tmp_path / "traffic" / "declared"
    module_dir.mkdir(parents=True)
    (module_dir / "module.yaml").write_text(
        "name: traffic.declared\ntype: traffic\nentrypoint: run.sh\n"
        "lifecycle:\n  start: '<kubeconfig>'\n",
        encoding="utf-8",
    )
    (module_dir / "run.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    module = load_module(tmp_path, "traffic/declared", expected_type="traffic")

    assert module.supports("start") is True
    assert module.supports("stop") is False


def test_missing_entrypoint_raises(tmp_path: Path) -> None:
    module_dir = tmp_path / "traffic" / "noentry"
    module_dir.mkdir(parents=True)
    (module_dir / "module.yaml").write_text("name: t\ntype: traffic\n", encoding="utf-8")

    with pytest.raises(ModuleError):
        load_module(tmp_path, "traffic/noentry", expected_type="traffic")


def test_arg_schema_defaults_to_empty_mapping() -> None:
    module = load_module(Path(".").resolve(), "traffic/online-boutique", expected_type="traffic")

    assert isinstance(module.arg_schema, dict)
    assert "shape" in module.arg_schema

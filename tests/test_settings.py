from __future__ import annotations

import pytest

from benchmark_platform import settings
from benchmark_platform.cli import main


@pytest.fixture(autouse=True)
def _no_variables(monkeypatch):
    for variable in settings.VARIABLES.values():
        monkeypatch.delenv(variable, raising=False)


def test_file_then_variable_priority(tmp_path, monkeypatch):
    assert settings.get("utils_path").source == "not set"
    settings.set_value("utils_path", [str(tmp_path / "u")])
    setting = settings.get("utils_path")
    assert setting.value == str(tmp_path / "u") and setting.source.startswith("file ")
    monkeypatch.setenv("BENCHMARK_UTILS_PATH", "/override")
    setting = settings.get("utils_path")
    assert setting.value == "/override" and setting.source == "variable BENCHMARK_UTILS_PATH"


def test_module_paths_list(tmp_path, monkeypatch):
    settings.set_value("module_paths", [str(tmp_path / "a"), str(tmp_path / "b")])
    assert settings.get("module_paths").value == [str(tmp_path / "a"), str(tmp_path / "b")]
    monkeypatch.setenv("BENCHMARK_MODULE_PATHS", "/x:/y")
    assert settings.get("module_paths").value == ["/x", "/y"]


def test_unset_and_require(tmp_path):
    settings.set_value("env", [str(tmp_path / "activate")])
    settings.unset("env")
    assert settings.get("env").value is None
    with pytest.raises(settings.SettingsError, match="config set module_paths"):
        settings.require("module_paths")


def test_benchmark_config_points_elsewhere(tmp_path, monkeypatch):
    other = tmp_path / "other.yaml"
    monkeypatch.setenv("BENCHMARK_CONFIG", str(other))
    settings.set_value("utils_path", [str(tmp_path)])
    assert other.is_file() and settings.config_file() == other


def test_cli_config(tmp_path, capsys):
    assert main(["config", "set", "utils_path", str(tmp_path)]) == 0
    assert main(["config", "get", "utils_path"]) == 0
    assert capsys.readouterr().out.strip().endswith(str(tmp_path))
    assert main(["config"]) == 0
    out = capsys.readouterr().out
    assert "utils_path" in out and "not set" in out  # module_paths and env
    assert main(["config", "get", "env"]) == 1  # not set


def test_module_paths_empty_element_means_file(tmp_path, monkeypatch):
    settings.set_value("module_paths", [str(tmp_path / "repo")])
    monkeypatch.setenv("BENCHMARK_MODULE_PATHS", "/mine")
    assert settings.get("module_paths").value == ["/mine"]  # replaces
    monkeypatch.setenv("BENCHMARK_MODULE_PATHS", "/mine:")
    assert settings.get("module_paths").value == ["/mine", str(tmp_path / "repo")]  # adds after
    monkeypatch.setenv("BENCHMARK_MODULE_PATHS", ":/mine")
    setting = settings.get("module_paths")
    assert setting.value == [str(tmp_path / "repo"), "/mine"]  # adds before
    assert "variable" in setting.source and "file" in setting.source


def test_default_file_is_in_the_installation(monkeypatch):
    import sys
    from pathlib import Path

    monkeypatch.delenv("BENCHMARK_CONFIG")
    assert settings.config_file() == Path(sys.prefix) / "benchmark-platform.yaml"


def test_add_and_remove_module_paths(tmp_path):
    a, b = str(tmp_path / "a"), str(tmp_path / "b")
    settings.set_value("module_paths", [a])
    settings.add_values("module_paths", [b, a])  # a already there: kept once
    assert settings.get("module_paths").value == [a, b]
    settings.remove_values("module_paths", [a])
    assert settings.get("module_paths").value == [b]
    with pytest.raises(settings.SettingsError, match="Not in module_paths"):
        settings.remove_values("module_paths", [a])
    with pytest.raises(settings.SettingsError, match="not a list"):
        settings.add_values("utils_path", [a])


def test_cli_config_add_remove(tmp_path, capsys):
    assert main(["config", "set", "module_paths", str(tmp_path / "a")]) == 0
    assert main(["config", "add", "module_paths", str(tmp_path / "b")]) == 0
    assert main(["config", "get", "module_paths"]) == 0
    assert capsys.readouterr().out.strip().endswith(f"{tmp_path / 'a'}:{tmp_path / 'b'}")
    assert main(["config", "remove", "module_paths", str(tmp_path / "a")]) == 0
    assert main(["config", "remove", "module_paths", str(tmp_path / "a")]) == 1

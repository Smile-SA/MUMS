from __future__ import annotations

import os

import pytest

from mums.settings import SettingsError, apply, describe


@pytest.fixture(autouse=True)
def _restore_environment():
    """apply() changes this process's environment: put it back after each test."""
    saved = dict(os.environ)
    yield
    os.environ.clear()
    os.environ.update(saved)


def test_unset_changes_nothing(monkeypatch):
    monkeypatch.delenv("MUMS_ENV", raising=False)
    before = dict(os.environ)
    apply()
    assert dict(os.environ) == before


def test_sourced_file_applies(tmp_path, monkeypatch):
    env_file = tmp_path / "activate"
    env_file.write_text(
        f'export PATH="{tmp_path}/bin:$PATH"\nexport VIRTUAL_ENV="{tmp_path}"\nunset GONE\n'
    )
    monkeypatch.setenv("MUMS_ENV", str(env_file))
    monkeypatch.setenv("GONE", "x")
    monkeypatch.setenv("PATH", os.environ["PATH"])
    apply()
    assert os.environ["PATH"].startswith(f"{tmp_path}/bin:")
    assert os.environ["VIRTUAL_ENV"] == str(tmp_path)
    assert "GONE" not in os.environ


def test_missing_or_failing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("MUMS_ENV", str(tmp_path / "nope"))
    with pytest.raises(SettingsError, match="not a file"):
        apply()
    bad = tmp_path / "bad"
    bad.write_text("echo oops >&2\nfalse\n")
    monkeypatch.setenv("MUMS_ENV", str(bad))
    with pytest.raises(SettingsError, match="failed: oops"):
        apply()


def test_apply_exports_paths_from_file_but_not_env(tmp_path, monkeypatch):
    from mums import settings

    for variable in settings.VARIABLES.values():
        monkeypatch.delenv(variable, raising=False)
    env_file = tmp_path / "activate"
    env_file.write_text("export FROM_ENV_FILE=1\n")
    settings.set_value("module_paths", [str(tmp_path / "m")])
    settings.set_value("utils_path", [str(tmp_path / "u")])
    settings.set_value("env", [str(env_file)])
    apply()
    assert os.environ["MUMS_MODULE_PATHS"] == str(tmp_path / "m")
    assert os.environ["MUMS_UTILS_PATH"] == str(tmp_path / "u")
    assert os.environ["FROM_ENV_FILE"] == "1"  # sourced
    assert "MUMS_ENV" not in os.environ  # applied, not passed on
    assert describe("utils_path").source.startswith("file ")  # as found before apply


def test_exec_runs_in_the_environment(tmp_path):
    import subprocess
    import sys

    env_file = tmp_path / "activate"
    env_file.write_text("export FROM_ENV_FILE=yes\n")
    environment = {**os.environ, "MUMS_ENV": str(env_file)}
    code = "import sys; from mums.cli import main; sys.exit(main(sys.argv[1:]))"
    result = subprocess.run(
        [sys.executable, "-c", code, "exec", "--", "sh", "-c", 'echo "$FROM_ENV_FILE"'],
        capture_output=True, text=True, env=environment, check=False,
    )
    assert result.returncode == 0 and result.stdout.strip() == "yes"

from __future__ import annotations

import os

import pytest

from benchmark_platform.environment import EnvironmentFileError, load_environment


def test_unset_changes_nothing(monkeypatch):
    monkeypatch.delenv("BENCHMARK_ENV", raising=False)
    before = dict(os.environ)
    assert load_environment() is None
    assert dict(os.environ) == before


def test_sourced_file_applies(tmp_path, monkeypatch):
    env_file = tmp_path / "activate"
    env_file.write_text(
        f'export PATH="{tmp_path}/bin:$PATH"\nexport VIRTUAL_ENV="{tmp_path}"\nunset GONE\n'
    )
    monkeypatch.setenv("BENCHMARK_ENV", str(env_file))
    monkeypatch.setenv("GONE", "x")
    monkeypatch.setenv("PATH", os.environ["PATH"])
    assert load_environment() == env_file
    assert os.environ["PATH"].startswith(f"{tmp_path}/bin:")
    assert os.environ["VIRTUAL_ENV"] == str(tmp_path)
    assert "GONE" not in os.environ


def test_missing_or_failing_file(tmp_path, monkeypatch):
    monkeypatch.setenv("BENCHMARK_ENV", str(tmp_path / "nope"))
    with pytest.raises(EnvironmentFileError, match="not a file"):
        load_environment()
    bad = tmp_path / "bad"
    bad.write_text("echo oops >&2\nfalse\n")
    monkeypatch.setenv("BENCHMARK_ENV", str(bad))
    with pytest.raises(EnvironmentFileError, match="failed: oops"):
        load_environment()

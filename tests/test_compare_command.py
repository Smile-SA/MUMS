from __future__ import annotations

import json

from benchmark_platform.cli import main


def _fake_util(utils, tmp_path):
    """A stand-in for the util `compare`: records the arguments it gets."""
    tool = utils / "compare" / "compare.py"
    tool.parent.mkdir(parents=True)
    record = tmp_path / "args.json"
    tool.write_text(
        "import json, sys\n"
        f"json.dump(sys.argv[1:], open({str(record)!r}, 'w'))\n"
    )
    return record


def test_runs_become_data_directories(tmp_path, monkeypatch):
    utils = tmp_path / "utils"
    record = _fake_util(utils, tmp_path)
    monkeypatch.setenv("BENCHMARK_UTILS_PATH", str(utils))
    monkeypatch.setenv("BENCHMARK_MODULE_PATHS", str(tmp_path))
    for name in ("ref", "a", "b"):
        (tmp_path / "runs" / name / "data").mkdir(parents=True)
    runs = tmp_path / "runs"
    assert main(["compare", str(runs / "ref"), str(runs / "[ab]"), "-c", "out.csv"]) == 0
    assert json.loads(record.read_text()) == [
        str(runs / "ref" / "data"), str(runs / "a" / "data"), str(runs / "b" / "data"),
        "-c", "out.csv",
    ]


def test_not_a_run_directory(tmp_path, monkeypatch, capsys):
    utils = tmp_path / "utils"
    _fake_util(utils, tmp_path)
    monkeypatch.setenv("BENCHMARK_UTILS_PATH", str(utils))
    monkeypatch.setenv("BENCHMARK_MODULE_PATHS", str(tmp_path))
    assert main(["compare", str(tmp_path / "nothing")]) == 1
    assert "not a run directory" in capsys.readouterr().err

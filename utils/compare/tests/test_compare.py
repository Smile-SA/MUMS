"""The util compare: single runs and groups of runs, on generated summaries."""

from __future__ import annotations

import csv
import importlib.util
import subprocess
import sys
from pathlib import Path

COMPARE = Path(__file__).resolve().parent.parent / "compare.py"
_spec = importlib.util.spec_from_file_location("compare_util", COMPARE)
assert _spec and _spec.loader
compare_util = importlib.util.module_from_spec(_spec)
sys.modules["compare_util"] = compare_util
_spec.loader.exec_module(compare_util)


def _run(root: Path, name: str, latency: float, errors: float) -> Path:
    summary = root / name / "data" / "summary" / "basic-evaluation.csv"
    summary.parent.mkdir(parents=True)
    with summary.open("w", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["metric", "value", "unit", "goal", "description"])
        writer.writerow(["latency_p95_seconds", latency, "seconds", "minimize", "p95"])
        writer.writerow(["server_error_rate", errors, "ratio", "minimize", "5xx"])
        writer.writerow(["requests", 100, "count", "none", "requests"])
    return summary.parent.parent  # the data directory


def _compare(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(COMPARE), *args], capture_output=True, text=True,
                          check=True)


def test_groups_give_medians_and_significant_verdicts(tmp_path):
    for i in range(5):
        _run(tmp_path, f"base-{i}", latency=0.50 + i / 100, errors=0.01 * (i % 2))
        _run(tmp_path, f"opt-{i}", latency=0.30 + i / 100, errors=0.01 * ((i + 1) % 2))
    out = tmp_path / "groups.csv"
    _compare("-g", "base", str(tmp_path / "base-*" / "data"),
             "-g", "opt", str(tmp_path / "opt-*" / "data"), "-c", str(out), "-v")
    rows = {r["metric"]: r for r in csv.DictReader(out.open())}
    latency = rows["latency_p95_seconds"]
    assert latency["runs"] == "5" and latency["reference_runs"] == "5"
    assert latency["median"] == "0.32" and latency["reference_median"] == "0.52"
    assert latency["verdict"] == "better" and float(latency["p_value"]) < 0.01
    assert rows["server_error_rate"]["verdict"] == "~"  # no significant difference
    assert rows["requests"]["verdict"] == ""  # no goal


def test_three_runs_per_group_are_never_significant(tmp_path):
    for i in range(3):
        _run(tmp_path, f"a-{i}", latency=1.0 + i, errors=0)
        _run(tmp_path, f"b-{i}", latency=10.0 + i, errors=0)
    out = tmp_path / "groups.csv"
    _compare("-g", "a", str(tmp_path / "a-*" / "data"), "-g", "b", str(tmp_path / "b-*" / "data"),
             "-c", str(out))
    latency = next(r for r in csv.DictReader(out.open()) if r["metric"] == "latency_p95_seconds")
    assert latency["verdict"] == "~" and float(latency["p_value"]) == 0.1


def test_single_runs_still_compared(tmp_path):
    ref = _run(tmp_path, "ref", latency=0.5, errors=0)
    other = _run(tmp_path, "other", latency=0.4, errors=0)
    out = tmp_path / "single.csv"
    _compare(str(ref), str(other), "-c", str(out))
    latency = next(r for r in csv.DictReader(out.open()) if r["metric"] == "latency_p95_seconds")
    assert latency["verdict"] == "better" and latency["change"] == "-20.0%"


def test_mann_whitney_exact_values():
    # Fully separated groups: the smallest two-sided p for 5 vs 5 is 2 / C(10, 5).
    p_value, direction = compare_util.mann_whitney([6, 7, 8, 9, 10], [1, 2, 3, 4, 5])
    assert abs(p_value - 2 / 252) < 1e-12 and direction < 0
    assert compare_util.mann_whitney([1, 2], [3]) is None

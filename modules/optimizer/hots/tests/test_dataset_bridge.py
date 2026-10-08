from __future__ import annotations

import csv
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

# dataset_bridge.py belongs to this module, not to the benchmark_platform
# package (module code stays in its own directory): load it from there.
_MODULE_PATH = Path(__file__).resolve().parent.parent / "dataset_bridge.py"
_spec = importlib.util.spec_from_file_location("dataset_bridge", _MODULE_PATH)
assert _spec and _spec.loader
dataset_bridge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dataset_bridge)

convert = dataset_bridge.convert
hots_data_config_snippet = dataset_bridge.hots_data_config_snippet

FIXTURE_RUN_DIR = Path(__file__).parent / "fixtures" / "sample_run"


def _read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def test_convert_excludes_daemonset_and_other_namespaces(tmp_path: Path) -> None:
    usage_path, _ = convert(FIXTURE_RUN_DIR, tmp_path, namespace="online-boutique")
    pods = {row["pod"] for row in _read_rows(usage_path)}
    assert pods == {"frontend-1", "cartservice-1"}
    assert "kindnet-1" not in pods  # DaemonSet, excluded by default


def test_convert_forward_fills_gaps_and_sorts_by_tick(tmp_path: Path) -> None:
    usage_path, _ = convert(FIXTURE_RUN_DIR, tmp_path, namespace="online-boutique")
    rows = _read_rows(usage_path)

    # Globally sorted by (timestamp, pod), not grouped by pod.
    keys = [(int(r["timestamp"]), r["pod"]) for r in rows]
    assert keys == sorted(keys)

    frontend_rows = [r for r in rows if r["pod"] == "frontend-1"]
    # timestamp 1015 has no recorded cpu_usage_rate in the fixture -- forward-filled
    # from the previous tick's value (0.05) rather than dropped or left blank.
    assert [r["timestamp"] for r in frontend_rows] == ["1000", "1015", "1030"]
    assert frontend_rows[1]["cpu_usage_rate"] == "0.05"
    assert frontend_rows[2]["cpu_usage_rate"] == "0.08"


def test_convert_writes_node_capacities(tmp_path: Path) -> None:
    _, node_meta_path = convert(FIXTURE_RUN_DIR, tmp_path, namespace="online-boutique")
    rows = {r["node"]: r["cpu_usage_rate"] for r in _read_rows(node_meta_path)}
    assert rows == {"node-a": "2.0", "node-b": "2.0"}


def test_hots_data_config_snippet_matches_convert_columns() -> None:
    snippet = hots_data_config_snippet("cpu_usage_rate")
    assert snippet == {
        "tick_field": "timestamp",
        "individual_field": "pod",
        "host_field": "node",
        "metrics": ["cpu_usage_rate"],
    }


@pytest.mark.skipif(
    shutil.which("hots") is None, reason="hots is not installed (optional integration)"
)
def test_converted_dataset_runs_through_real_hots(tmp_path: Path) -> None:
    """Real integration test: platform dataset -> hots_bridge -> a real HOTS
    run (file connector, no Kafka/Kind needed) -> moves out."""
    convert(FIXTURE_RUN_DIR, tmp_path, namespace="online-boutique")

    config = {
        "time_limit": None,
        "data": hots_data_config_snippet("cpu_usage_rate"),
        "clustering": {
            "method": "kmeans",
            "nb_clusters": 1,
            "parameters": {"nb_clusters": 1},
        },
        "optimization": {"backend": "pyomo", "parameters": {"solver": "glpk", "verbose": 0}},
        "problem": {
            "type": "placement",
            "parameters": {"initial_placement": False, "tol": 0.1, "tol_move": 0.5},
        },
        "connector": {
            "type": "file",
            "parameters": {
                "data_folder": str(tmp_path),
                "file_name": "container_usage.csv",
                "sep_time": 1000,
                "tick_increment": 15,
                "window_duration": 3,
                "outfile": str(tmp_path / "moves.log"),
            },
        },
        "logging": {
            "level": "INFO",
            "filename": str(tmp_path / "hots.log"),
            "fmt": "%(asctime)s %(levelname)s: %(message)s",
        },
        "reporting": {
            "results_folder": str(tmp_path),
            "metrics_file": str(tmp_path / "metrics.csv"),
            "plots_folder": str(tmp_path / "plots"),
        },
        "visualization": {"enabled": False},
    }
    config_path = tmp_path / "hots-config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    result = subprocess.run(
        ["hots", "--config", str(config_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert (tmp_path / "metrics.csv").exists()
    assert (tmp_path / "moves.log").exists()

"""basic-evaluation: the node_metrics and namespaces options, on a small data dir."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

EVALUATE = Path(__file__).resolve().parent.parent / "evaluate.py"


def _write(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(header)
        writer.writerows(rows)


def _data_dir(tmp_path: Path) -> Path:
    data = tmp_path / "data"
    _write(data / "run-window" / "run-window.csv", ["start", "end"], [[100, 200]])
    _write(
        data / "http-requests" / "000001.csv",
        ["timestamp", "method", "endpoint", "status_code", "response_time_seconds",
         "no_response_reason"],
        [[110 + i, "GET", "/", 200, 0.1, ""] for i in range(10)],
    )
    tables = data / "essential-tables"
    _write(tables / "node_metadata" / "000001.csv", ["node", "taints"],
           [["w1", "[]"], ["w2", "[]"]])
    _write(
        tables / "node_timeseries" / "000001.csv",
        ["timestamp", "node", "cpu_usage_ratio", "memory_used_bytes", "memory_total_bytes"],
        [[t, n, 0.5, 1, 2] for t in range(110, 200, 15) for n in ("w1", "w2")],
    )
    _write(
        tables / "controller_timeseries" / "000001.csv",
        ["timestamp", "controller_kind", "controller_name", "namespace", "replicas_desired",
         "replicas_ready"],
        [[t, "Deployment", "frontend", "shop", 1, 1] for t in range(110, 200, 15)]
        + [[t, "Deployment", "prometheus", "monitoring", 1, 0] for t in range(110, 200, 15)],
    )
    return data


def _summary(data: Path, *options: str) -> dict[str, float]:
    subprocess.run([sys.executable, str(EVALUATE), str(data), *options], check=True,
                   capture_output=True)
    with (data / "summary" / "basic-evaluation.csv").open(newline="") as stream:
        return {row["metric"]: float(row["value"]) for row in csv.DictReader(stream)}


def test_defaults_report_node_metrics_and_all_namespaces(tmp_path):
    summary = _summary(_data_dir(tmp_path))
    assert "node_cpu_usage_mean" in summary
    assert summary["availability_mean"] == 0.5  # shop ready, monitoring not


def test_node_metrics_false_and_namespaces(tmp_path):
    summary = _summary(_data_dir(tmp_path), "--node-metrics", "false", "--namespaces", "shop")
    assert not any(metric.startswith("node") for metric in summary)
    assert summary["availability_mean"] == 1.0
    assert summary["requests"] == 10

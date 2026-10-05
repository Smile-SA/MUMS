#!/usr/bin/env python3
"""
evaluate.py
Summarizes one run from standard data, into
<data_dir>/summary/basic-evaluation.csv
(columns: metric, value, unit, goal, description).

Inputs (each optional: missing data gives no metric):
  <data_dir>/http-requests/*.csv     requests seen by the load generator
  <data_dir>/essential-tables/...    node usage and taints, controllers
  <data_dir>/run-window/run-window.csv

Usage: evaluate.py <data_dir> [--run-window true|false]
"""

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

OVERLOAD_THRESHOLD = 0.9  # usage of a node's machine (CPU or memory)
SUMMARY_NAME = "basic-evaluation.csv"


def read_table(directory: Path):
    if not directory.is_dir():
        return []
    rows = []
    for path in sorted(directory.glob("*.csv")):
        with path.open(newline="", encoding="utf-8") as stream:
            rows.extend(csv.DictReader(stream))
    return rows


def num(value):
    try:
        return float(value) if value not in ("", None) else None
    except ValueError:
        return None


def quantile(sorted_values, q):
    """Quantile by linear interpolation (sorted input)."""
    if not sorted_values:
        return None
    pos = (len(sorted_values) - 1) * q
    low, high = int(pos), min(int(pos) + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (pos - low)


class Summary:
    def __init__(self):
        self.rows = []

    def add(self, metric, value, unit, goal, description):
        if value is None:
            return
        self.rows.append([metric, f"{value:.6g}", unit, goal, description])

    def write(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.writer(stream)
            writer.writerow(["metric", "value", "unit", "goal", "description"])
            writer.writerows(self.rows)


def run_window(data_dir: Path):
    rows = read_table(data_dir / "run-window")
    if not rows:
        return None
    return num(rows[0]["start"]), num(rows[0]["end"])


def traffic_metrics(summary, data_dir, window):
    requests = read_table(data_dir / "http-requests")
    if window:
        requests = [r for r in requests if window[0] <= (num(r["timestamp"]) or 0) <= window[1]]
    if not requests:
        return
    times = [num(r["timestamp"]) for r in requests]
    duration = (window[1] - window[0]) if window else (max(times) - min(times))
    total = len(requests)
    answered = [r for r in requests if r["status_code"]]
    latencies = sorted(
        v for v in (num(r["response_time_seconds"]) for r in answered) if v is not None
    )
    server_errors = sum(1 for r in answered if r["status_code"].startswith("5"))
    client_errors = sum(1 for r in answered if r["status_code"].startswith("4"))
    no_response = [r for r in requests if not r["status_code"]]

    summary.add("duration", duration, "seconds", "none", "Duration over which requests are counted")
    summary.add("requests", total, "count", "none", "Requests sent")
    if duration > 0:
        summary.add("requests_per_second", total / duration, "count/second", "none",
                    "Requests sent per second (depends on the load shape)")
    summary.add("latency_mean_seconds", statistics.fmean(latencies) if latencies else None,
                "seconds", "minimize", "Mean response time (answered requests)")
    for q, name in ((0.5, "p50"), (0.95, "p95"), (0.99, "p99")):
        summary.add(f"latency_{name}_seconds", quantile(latencies, q), "seconds", "minimize",
                    f"{name} of response times (answered requests)")
    summary.add("latency_max_seconds", latencies[-1] if latencies else None, "seconds",
                "minimize", "Slowest response time")
    summary.add("server_error_rate", server_errors / total, "ratio", "minimize",
                "Share of requests answered with a 5xx status")
    summary.add("client_error_rate", client_errors / total, "ratio", "minimize",
                "Share of requests answered with a 4xx status")
    summary.add("no_response_rate", len(no_response) / total, "ratio", "minimize",
                "Share of requests without any response")
    for reason in ("timeout", "connection_refused", "connection_reset", "other"):
        count = sum(1 for r in no_response if r["no_response_reason"] == reason)
        summary.add(f"no_response_{reason}_rate", count / total, "ratio", "minimize",
                    f"Share of requests without response, reason: {reason}")


def schedulable_nodes(node_meta):
    """Nodes that take workload: no NoSchedule / NoExecute taint (e.g. not a
    control-plane node)."""
    return {
        row["node"] for row in node_meta
        if not any(f'"{effect}"' in row.get("taints", "") for effect in ("NoSchedule", "NoExecute"))
    }


def node_metrics(summary, data_dir, window):
    """Usage of the nodes taking workload, from node-level metrics: CPU usage of
    the machine, memory used / total memory of the machine."""
    tables = data_dir / "essential-tables"
    nodes = schedulable_nodes(read_table(tables / "node_metadata"))
    rows = read_table(tables / "node_timeseries")
    if window:
        rows = [r for r in rows if window[0] <= (num(r["timestamp"]) or 0) <= window[1]]
    samples = defaultdict(list)  # node -> [(timestamp, cpu ratio, memory ratio)]
    for r in rows:
        if r["node"] not in nodes:
            continue
        cpu = num(r["cpu_usage_ratio"])
        used, total = num(r["memory_used_bytes"]), num(r.get("memory_total_bytes"))
        mem = used / total if used is not None and total else None
        if cpu is not None or mem is not None:
            samples[r["node"]].append((num(r["timestamp"]), cpu, mem))
    if not samples:
        return

    # Nodes are measured at different instants: at regular instants (every
    # typical sample spacing), each node contributes its latest measure, if less
    # than 1.5 spacing old.
    gaps = []
    for points in samples.values():
        points.sort(key=lambda x: x[0])
        ts = [t for t, *_ in points]
        gaps.extend(b - a for a, b in zip(ts, ts[1:], strict=False) if b > a)
    step = statistics.median(gaps) if gaps else 1.0
    max_age = 1.5 * step
    first = min(p[0][0] for p in samples.values())
    last = max(p[-1][0] for p in samples.values())

    cpu_ratios, mem_ratios, cpu_imbalance, mem_imbalance = [], [], [], []
    overloaded = instants = 0
    t = min(first + step, last)
    while t <= last + 1e-9:
        cpu_now, mem_now = {}, {}
        for node, points in samples.items():
            recent = [p for p in points if t - max_age < p[0] <= t]
            cpu = next((p[1] for p in reversed(recent) if p[1] is not None), None)
            mem = next((p[2] for p in reversed(recent) if p[2] is not None), None)
            if cpu is not None:
                cpu_now[node] = cpu
            if mem is not None:
                mem_now[node] = mem
        if cpu_now or mem_now:
            instants += 1
            cpu_ratios.extend(cpu_now.values())
            mem_ratios.extend(mem_now.values())
            if len(cpu_now) == len(samples) > 1:
                cpu_imbalance.append(statistics.pstdev(cpu_now.values()))
            if len(mem_now) == len(samples) > 1:
                mem_imbalance.append(statistics.pstdev(mem_now.values()))
            if any(v > OVERLOAD_THRESHOLD for v in [*cpu_now.values(), *mem_now.values()]):
                overloaded += 1
        t += step

    summary.add("nodes", len(samples), "count", "none",
                "Nodes taking workload (no NoSchedule / NoExecute taint)")
    for name, values, what in (("cpu", cpu_ratios, "CPU"), ("memory", mem_ratios, "memory")):
        if values:
            summary.add(f"node_{name}_usage_mean", statistics.fmean(values), "ratio", "none",
                        f"Mean {what} usage of the nodes' machines")
            summary.add(f"node_{name}_usage_max", max(values), "ratio", "minimize",
                        f"Highest {what} usage of a node's machine")
    for name, values, what in (("cpu", cpu_imbalance, "CPU"), ("memory", mem_imbalance, "memory")):
        if values:
            summary.add(f"node_{name}_imbalance_mean", statistics.fmean(values), "ratio",
                        "minimize", f"Mean std. dev. of {what} usage across nodes")
    if instants:
        summary.add("node_overload_time_ratio", overloaded / instants, "ratio", "minimize",
                    f"Share of time with a node above {OVERLOAD_THRESHOLD:.0%} of its machine's "
                    "CPU or memory")


def availability_metrics(summary, data_dir, window):
    rows = read_table(data_dir / "essential-tables" / "controller_timeseries")
    if window:
        rows = [r for r in rows if window[0] <= (num(r["timestamp"]) or 0) <= window[1]]
    ratios = []
    for r in rows:
        desired, ready = num(r["replicas_desired"]), num(r["replicas_ready"])
        if r["controller_kind"] == "Deployment" and desired and ready is not None:
            ratios.append(min(ready / desired, 1.0))
    if ratios:
        summary.add("availability_mean", statistics.fmean(ratios), "ratio", "maximize",
                    "Mean ready / desired replicas of Deployments")
        summary.add("availability_min", min(ratios), "ratio", "maximize",
                    "Lowest ready / desired replicas of a Deployment")


def main():
    parser = argparse.ArgumentParser(description="Summarize a run from standard data.")
    parser.add_argument("data_dir", type=Path)
    parser.add_argument("--run-window", choices=("true", "false"), default="true")
    args = parser.parse_args()

    window = run_window(args.data_dir) if args.run_window == "true" else None
    summary = Summary()
    traffic_metrics(summary, args.data_dir, window)
    node_metrics(summary, args.data_dir, window)
    availability_metrics(summary, args.data_dir, window)
    summary.write(args.data_dir / "summary" / SUMMARY_NAME)
    print(f"=== {len(summary.rows)} metric(s) written to summary/{SUMMARY_NAME} ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

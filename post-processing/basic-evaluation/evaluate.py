#!/usr/bin/env python3
"""
evaluate.py
Summarizes one run from standard data, into
<data_dir>/summary/post-processing.basic-evaluation.csv
(columns: metric, value, unit, goal, description).

Inputs (each optional: missing data gives no metric):
  <data_dir>/http-requests/*.csv     requests seen by the load generator
  <data_dir>/essential-tables/...    pod usage, node allocatable, controllers
  <data_dir>/run-window/run-window.csv

Usage: evaluate.py <data_dir> [--run-window true|false]
"""

import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

OVERLOAD_THRESHOLD = 0.9  # node usage / allocatable
SUMMARY_NAME = "post-processing.basic-evaluation.csv"


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
    summary.add("requests", total, "requests", "none", "Requests sent")
    if duration > 0:
        summary.add("requests_per_second", total / duration, "requests/second", "none",
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
    nodes = {}
    for row in node_meta:
        taints = row.get("taints", "")
        if '"NoSchedule"' in taints or '"NoExecute"' in taints:
            continue
        cpu, memory = num(row["cpu_allocatable"]), num(row["memory_allocatable"])
        if cpu and memory:
            nodes[row["node"]] = (cpu, memory)
    return nodes


def node_metrics(summary, data_dir, window):
    tables = data_dir / "essential-tables"
    nodes = schedulable_nodes(read_table(tables / "node_metadata"))
    pod_usage = read_table(tables / "pod_timeseries")
    if window:
        pod_usage = [r for r in pod_usage if window[0] <= (num(r["timestamp"]) or 0) <= window[1]]
    if not nodes or not pod_usage:
        return

    # A node's usage at an instant is the sum of its pods' usage at that instant.
    # Pods are measured at different instants, so at regular instants (every
    # typical sample spacing) each pod contributes its latest measure, if it is
    # recent enough (less than 1.5 spacing old): every pod still measured is
    # counted once, and a pod no longer measured drops out quickly.
    by_pod = defaultdict(list)  # (ns, pod) -> [(timestamp, node, cpu, memory)], usage rows only
    for r in pod_usage:
        cpu, mem = num(r["cpu_usage_rate"]), num(r["memory_working_set_bytes"])
        if (cpu is not None or mem is not None) and r["node"] in nodes:
            by_pod[(r["namespace"], r["pod"])].append((num(r["timestamp"]), r["node"], cpu, mem))
    if not by_pod:
        return
    gaps = []
    for samples in by_pod.values():
        samples.sort(key=lambda x: x[0])
        ts = sorted({t for t, *_ in samples})
        gaps.extend(b - a for a, b in zip(ts, ts[1:], strict=False) if b > a)
    step = statistics.median(gaps) if gaps else 1.0
    max_age = 1.5 * step
    first = min(s[0][0] for s in by_pod.values())
    last = max(s[-1][0] for s in by_pod.values())

    cpu_ratios, mem_ratios, cpu_imbalance, mem_imbalance = [], [], [], []
    overloaded = instants = 0
    cursor = {key: 0 for key in by_pod}
    latest = {}  # (ns, pod) -> (timestamp, node, cpu, memory): latest cpu / memory seen so far
    # Start one spacing in: by then, every pod has been measured once.
    t = min(first + step, last)
    while t <= last + 1e-9:
        for key, samples in by_pod.items():
            i = cursor[key]
            while i < len(samples) and samples[i][0] <= t:
                ts_, node, cpu, mem = samples[i]
                prev = latest.get(key, (None, node, None, None))
                latest[key] = (ts_, node, cpu if cpu is not None else prev[2],
                               mem if mem is not None else prev[3])
                i += 1
            cursor[key] = i
        cpu_by_node, mem_by_node = defaultdict(float), defaultdict(float)
        seen_cpu, seen_mem = set(), set()
        for ts_, node, cpu, mem in latest.values():
            if t - ts_ >= max_age:
                continue
            if cpu is not None:
                cpu_by_node[node] += cpu
                seen_cpu.add(node)
            if mem is not None:
                mem_by_node[node] += mem
                seen_mem.add(node)
        cpu_r = {n: cpu_by_node[n] / nodes[n][0] for n in seen_cpu}
        mem_r = {n: mem_by_node[n] / nodes[n][1] for n in seen_mem}
        if cpu_r or mem_r:
            instants += 1
            cpu_ratios.extend(cpu_r.values())
            mem_ratios.extend(mem_r.values())
            if len(cpu_r) == len(nodes) and len(nodes) > 1:
                cpu_imbalance.append(statistics.pstdev(cpu_r.values()))
            if len(mem_r) == len(nodes) and len(nodes) > 1:
                mem_imbalance.append(statistics.pstdev(mem_r.values()))
            if any(v > OVERLOAD_THRESHOLD for v in [*cpu_r.values(), *mem_r.values()]):
                overloaded += 1
        t += step

    summary.add("nodes", len(nodes), "nodes", "none", "Nodes taking workload (no NoSchedule taint)")
    for name, values, what in (("cpu", cpu_ratios, "CPU"), ("memory", mem_ratios, "memory")):
        if values:
            summary.add(f"node_{name}_usage_mean", statistics.fmean(values), "ratio", "none",
                        f"Mean {what} usage of nodes (sum of their pods / allocatable)")
            summary.add(f"node_{name}_usage_max", max(values), "ratio", "minimize",
                        f"Highest {what} usage of a node (sum of its pods / allocatable)")
    for name, values, what in (("cpu", cpu_imbalance, "CPU"), ("memory", mem_imbalance, "memory")):
        if values:
            summary.add(f"node_{name}_imbalance_mean", statistics.fmean(values), "ratio",
                        "minimize", f"Mean std. dev. of {what} usage across nodes")
    if instants:
        summary.add("node_overload_time_ratio", overloaded / instants, "ratio", "minimize",
                    f"Share of time with a node above {OVERLOAD_THRESHOLD:.0%} of its CPU or "
                    "memory allocatable")


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

#!/usr/bin/env python3
"""
node_timeseries.py
stdin  : OpenMetrics scrapes (cat <data_dir>/openmetrics/*.om)
stdout : node_timeseries.csv

Key    : (timestamp, node)
Columns: timestamp, node, cpu_usage_ratio, memory_used_bytes,
           memory_allocatable_bytes, cpu_pressure_waiting_seconds_total,
           memory_pressure_waiting_seconds_total,
           memory_pressure_stalled_seconds_total,
           condition_ready, unschedulable, up

cpu_usage_ratio = 1 - (delta_idle / delta_total_all_modes)
memory_used = MemTotal - MemAvailable
"""

import csv
import re
import sys
from collections import defaultdict

METRICS = {
    "node_cpu_seconds_total",
    "node_memory_MemTotal_bytes",
    "node_memory_MemAvailable_bytes",
    "node_pressure_cpu_waiting_seconds_total",
    "node_pressure_memory_waiting_seconds_total",
    "node_pressure_memory_stalled_seconds_total",
    "kube_node_status_allocatable",
    "kube_node_status_condition",
    "kube_node_spec_unschedulable",
    "up",
}

CPU_MODES = ("user", "system", "nice", "iowait", "irq", "softirq", "steal", "idle")


def seconds(ms):
    """Prometheus sample timestamp (Unix milliseconds) -> Unix seconds."""
    return f"{ms / 1000:.3f}"


def parse_labels(s):
    return dict(re.findall(r'(\w+)="([^"]*)"', s))


def parse_line(line):
    line = line.strip()
    if not line or line.startswith("#"):
        return None
    m = re.match(r"^(\w+)\{([^}]*)\}\s+([\d.eE+\-]+)\s+(\d+)$", line)
    if not m:
        return None
    name = m.group(1)
    if name not in METRICS:
        return None
    return name, parse_labels(m.group(2)), float(m.group(3)), int(m.group(4))


def get_node(labels):
    return labels.get("node") or labels.get("kubernetes_io_hostname") or labels.get("instance", "")


def main():
    # data[(node, ts)][field] = value
    data = defaultdict(dict)

    for line in sys.stdin:
        parsed = parse_line(line)
        if not parsed:
            continue
        name, labels, value, ts = parsed

        # 'up' : on ne garde que le job kubernetes-nodes
        if name == "up" and labels.get("job") != "kubernetes-nodes":
            continue

        node = get_node(labels)
        if not node:
            continue

        key = (node, ts)

        if name == "node_cpu_seconds_total":
            mode = labels.get("mode", "")
            if mode in CPU_MODES:
                # One series per core: kept per (core, mode), summed below. Keyed so
                # that the same sample read from several scrapes is counted once.
                data[key].setdefault("cpu_cores", {})[(labels.get("cpu", ""), mode)] = value

        elif name == "node_memory_MemTotal_bytes":
            data[key]["mem_total"] = value

        elif name == "node_memory_MemAvailable_bytes":
            data[key]["mem_available"] = value

        elif name == "node_pressure_cpu_waiting_seconds_total":
            data[key]["cpu_pressure_waiting"] = value

        elif name == "node_pressure_memory_waiting_seconds_total":
            data[key]["mem_pressure_waiting"] = value

        elif name == "node_pressure_memory_stalled_seconds_total":
            data[key]["mem_pressure_stalled"] = value

        elif name == "kube_node_status_allocatable":
            if labels.get("resource") == "memory":
                data[key]["mem_allocatable"] = value

        elif name == "kube_node_status_condition":
            if labels.get("condition") == "Ready" and labels.get("status") == "true":
                data[key]["condition_ready"] = int(value)

        elif name == "kube_node_spec_unschedulable":
            data[key]["unschedulable"] = int(value)

        elif name == "up":
            data[key]["up"] = int(value)

    # Sum CPU time over the node's cores, per mode.
    for metrics in data.values():
        cores = metrics.pop("cpu_cores", None)
        if cores:
            for (_core, mode), value in cores.items():
                metrics[f"cpu_{mode}"] = metrics.get(f"cpu_{mode}", 0) + value

    # Regrouper par nœud, trier par timestamp
    by_node = defaultdict(list)
    for (node, ts), metrics in data.items():
        by_node[node].append((ts, metrics))

    writer = csv.writer(sys.stdout)
    writer.writerow(
        [
            "timestamp",
            "node",
            "cpu_usage_ratio",
            "memory_used_bytes",
            "memory_allocatable_bytes",
            "cpu_pressure_waiting_seconds_total",
            "memory_pressure_waiting_seconds_total",
            "memory_pressure_stalled_seconds_total",
            "condition_ready",
            "unschedulable",
            "up",
        ]
    )

    for node, points in by_node.items():
        points.sort(key=lambda x: x[0])
        # Last CPU counters seen for this node: node-exporter and
        # kube-state-metrics samples do not share timestamps, so the previous
        # row may carry no CPU data at all.
        last_cpu = None

        for ts, metrics in points:
            # CPU usage ratio: 1 - (idle time / total time) since the last CPU sample.
            cpu_usage_ratio = ""
            cpu_now = {m: metrics[f"cpu_{m}"] for m in CPU_MODES if f"cpu_{m}" in metrics}
            if cpu_now:
                if last_cpu is not None:
                    deltas = {m: cpu_now.get(m, 0) - last_cpu.get(m, 0) for m in CPU_MODES}
                    total_delta = sum(deltas.values())
                    # A negative delta means the counters restarted (node-exporter
                    # restart): no ratio for this sample.
                    if total_delta > 0 and all(d >= 0 for d in deltas.values()):
                        cpu_usage_ratio = 1.0 - (deltas.get("idle", 0) / total_delta)
                last_cpu = cpu_now

            # Memory used = MemTotal - MemAvailable
            mem_total = metrics.get("mem_total", "")
            mem_available = metrics.get("mem_available", "")
            if mem_total != "" and mem_available != "":
                memory_used = mem_total - mem_available
            else:
                memory_used = ""

            writer.writerow(
                [
                    seconds(ts),
                    node,
                    cpu_usage_ratio,
                    memory_used,
                    metrics.get("mem_allocatable", ""),
                    metrics.get("cpu_pressure_waiting", ""),
                    metrics.get("mem_pressure_waiting", ""),
                    metrics.get("mem_pressure_stalled", ""),
                    metrics.get("condition_ready", ""),
                    metrics.get("unschedulable", ""),
                    metrics.get("up", ""),
                ]
            )



if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
node_timeseries.py
stdin  : metrics.om (OpenMetrics)
stdout : node_timeseries.csv

Clé    : (timestamp, node)
Colonnes : timestamp, node, cpu_usage_ratio, memory_used_bytes,
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
                data[key][f"cpu_{mode}"] = value

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
        prev_ts = None
        prev = {}

        for ts, metrics in points:
            dt = (ts - prev_ts) / 1000.0 if prev_ts is not None else None

            # CPU usage ratio
            cpu_usage_ratio = ""
            if dt and prev:
                total_delta = sum(
                    metrics.get(f"cpu_{m}", 0) - prev.get(f"cpu_{m}", 0) for m in CPU_MODES
                )
                idle_delta = metrics.get("cpu_idle", 0) - prev.get("cpu_idle", 0)
                if total_delta > 0:
                    cpu_usage_ratio = 1.0 - (idle_delta / total_delta)

            # Mémoire utilisée
            mem_total = metrics.get("mem_total", "")
            mem_available = metrics.get("mem_available", "")
            if mem_total != "" and mem_available != "":
                memory_used = mem_total - mem_available
            else:
                memory_used = ""

            writer.writerow(
                [
                    ts,
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

            prev_ts = ts
            prev = metrics


if __name__ == "__main__":
    main()

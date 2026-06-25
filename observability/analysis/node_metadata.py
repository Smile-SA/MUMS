#!/usr/bin/env python3
"""
node_metadata.py
stdin  : metrics.om (OpenMetrics)
stdout : node_metadata.csv

Clé    : node
Colonnes : node, cpu_allocatable, memory_allocatable,
           architecture, os, kernel_version, taints, created_time

taints est sérialisé en JSON : [{"key": ..., "effect": ..., "value": ...}, ...]
"""

import csv
import json
import re
import sys
from collections import defaultdict

METRICS = {
    "kube_node_status_allocatable",
    "kube_node_info",
    "kube_node_spec_taint",
    "kube_node_created",
}


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


def main():
    nodes = defaultdict(dict)
    taints = defaultdict(list)  # node -> [{key, effect, value}, ...]

    for line in sys.stdin:
        parsed = parse_line(line)
        if not parsed:
            continue
        name, labels, value, ts = parsed

        node = labels.get("node", "")
        if not node:
            continue

        if name == "kube_node_status_allocatable":
            resource = labels.get("resource", "")
            if resource == "cpu":
                nodes[node]["cpu_allocatable"] = value
            elif resource == "memory":
                nodes[node]["memory_allocatable"] = value

        elif name == "kube_node_info":
            nodes[node]["architecture"] = labels.get("architecture", "")
            nodes[node]["os"] = labels.get("os", "")
            nodes[node]["kernel_version"] = labels.get("kernel_version", "")

        elif name == "kube_node_spec_taint":
            if value == 1:
                taint = {
                    "key": labels.get("key", ""),
                    "effect": labels.get("effect", ""),
                    "value": labels.get("value", ""),
                }
                if taint not in taints[node]:
                    taints[node].append(taint)

        elif name == "kube_node_created":
            nodes[node]["created_time"] = value

    writer = csv.writer(sys.stdout)
    writer.writerow(
        [
            "node",
            "cpu_allocatable",
            "memory_allocatable",
            "architecture",
            "os",
            "kernel_version",
            "taints",
            "created_time",
        ]
    )

    for node, info in nodes.items():
        writer.writerow(
            [
                node,
                info.get("cpu_allocatable", ""),
                info.get("memory_allocatable", ""),
                info.get("architecture", ""),
                info.get("os", ""),
                info.get("kernel_version", ""),
                json.dumps(taints.get(node, [])),
                info.get("created_time", ""),
            ]
        )


if __name__ == "__main__":
    main()

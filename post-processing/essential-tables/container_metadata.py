#!/usr/bin/env python3
"""
container_metadata.py
stdin  : OpenMetrics scrapes (cat <data_dir>/openmetrics/*.om)
stdout : container_metadata.csv

Key    : (pod, namespace, container)
Columns: pod, namespace, container, image,
         cpu_request, memory_request, cpu_limit, memory_limit
"""

import csv
import re
import sys
from collections import defaultdict

METRICS = {
    "kube_pod_container_info",
    "kube_pod_container_resource_requests",
    "kube_pod_container_resource_limits",
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
    containers = defaultdict(dict)

    for line in sys.stdin:
        parsed = parse_line(line)
        if not parsed:
            continue
        name, labels, value, ts = parsed

        pod = labels.get("pod", "")
        ns = labels.get("namespace", "")
        ctr = labels.get("container", "")
        if not pod or not ns or not ctr:
            continue

        key = (pod, ns, ctr)

        if name == "kube_pod_container_info":
            containers[key]["image"] = labels.get("image", "")

        elif name == "kube_pod_container_resource_requests":
            resource = labels.get("resource", "")
            if resource == "cpu":
                containers[key]["cpu_request"] = value
            elif resource == "memory":
                containers[key]["memory_request"] = value

        elif name == "kube_pod_container_resource_limits":
            resource = labels.get("resource", "")
            if resource == "cpu":
                containers[key]["cpu_limit"] = value
            elif resource == "memory":
                containers[key]["memory_limit"] = value

    writer = csv.writer(sys.stdout)
    writer.writerow(
        [
            "pod",
            "namespace",
            "container",
            "image",
            "cpu_request",
            "memory_request",
            "cpu_limit",
            "memory_limit",
        ]
    )

    for (pod, ns, ctr), info in containers.items():
        writer.writerow(
            [
                pod,
                ns,
                ctr,
                info.get("image", ""),
                info.get("cpu_request", ""),
                info.get("memory_request", ""),
                info.get("cpu_limit", ""),
                info.get("memory_limit", ""),
            ]
        )


if __name__ == "__main__":
    main()

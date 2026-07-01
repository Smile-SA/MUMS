#!/usr/bin/env python3
"""
controller_metadata.py
stdin  : metrics.om (OpenMetrics)
stdout : controller_metadata.csv

Key    : (controller_kind, controller_name, namespace)
Columns: controller_kind, controller_name, namespace,
         parent_kind, parent_name, replicas_desired

Supports: ReplicaSet (with parent Deployment), StatefulSet, DaemonSet, Job
"""

import csv
import re
import sys
from collections import defaultdict

METRICS = {
    "kube_replicaset_owner",
    "kube_replicaset_spec_replicas",
    "kube_statefulset_replicas",
    "kube_daemonset_status_desired_number_scheduled",
    "kube_job_spec_parallelism",
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
    # controllers[(kind, name, ns)] = {parent_kind, parent_name, replicas_desired}
    controllers = defaultdict(dict)

    for line in sys.stdin:
        parsed = parse_line(line)
        if not parsed:
            continue
        name, labels, value, ts = parsed

        ns = labels.get("namespace", "")

        if name == "kube_replicaset_owner":
            rs = labels.get("replicaset", "")
            if not rs or not ns:
                continue
            key = ("ReplicaSet", rs, ns)
            controllers[key]["parent_kind"] = labels.get("owner_kind", "")
            controllers[key]["parent_name"] = labels.get("owner_name", "")

        elif name == "kube_replicaset_spec_replicas":
            rs = labels.get("replicaset", "")
            if not rs or not ns:
                continue
            key = ("ReplicaSet", rs, ns)
            controllers[key].setdefault("replicas_desired", value)

        elif name == "kube_statefulset_replicas":
            sts = labels.get("statefulset", "")
            if not sts or not ns:
                continue
            key = ("StatefulSet", sts, ns)
            controllers[key].setdefault("replicas_desired", value)

        elif name == "kube_daemonset_status_desired_number_scheduled":
            ds = labels.get("daemonset", "")
            if not ds or not ns:
                continue
            key = ("DaemonSet", ds, ns)
            controllers[key].setdefault("replicas_desired", value)

        elif name == "kube_job_spec_parallelism":
            job = labels.get("job_name", "")
            if not job or not ns:
                continue
            key = ("Job", job, ns)
            controllers[key].setdefault("replicas_desired", value)

    writer = csv.writer(sys.stdout)
    writer.writerow(
        [
            "controller_kind",
            "controller_name",
            "namespace",
            "parent_kind",
            "parent_name",
            "replicas_desired",
        ]
    )

    for (kind, ctrl_name, ns), info in controllers.items():
        writer.writerow(
            [
                kind,
                ctrl_name,
                ns,
                info.get("parent_kind", ""),
                info.get("parent_name", ""),
                info.get("replicas_desired", ""),
            ]
        )


if __name__ == "__main__":
    main()

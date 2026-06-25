#!/usr/bin/env python3
"""
pod_metadata.py
stdin  : metrics.om (OpenMetrics)
stdout : pod_metadata.csv

Clé    : (pod, namespace)
Colonnes : pod, namespace, node, controller_kind, controller_name,
           qos_class, created_time, scheduled_time, running_time,
           ready_time, succeeded_time, failed_time

Notes :
  - created_time, scheduled_time, running_time, ready_time sont des timestamps
    Unix (secondes) portés par la valeur de la métrique elle-même.
  - succeeded_time et failed_time sont approximés par le premier timestamp de
    scrape où la phase correspondante est observée (valeur = 1), faute de
    métrique de timestamp dédiée.
"""

import csv
import re
import sys
from collections import defaultdict

METRICS = {
    "kube_pod_info",
    "kube_pod_owner",
    "kube_pod_status_qos_class",
    "kube_pod_created",
    "kube_pod_status_scheduled_time",
    "kube_pod_status_initialized_time",
    "kube_pod_status_ready_time",
    "kube_pod_status_phase",
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
    pods = defaultdict(dict)
    # Premier timestamp de scrape où phase=Succeeded/Failed est observé
    phase_first_scrape = defaultdict(dict)  # (pod, ns) -> {phase: scrape_ts}

    for line in sys.stdin:
        parsed = parse_line(line)
        if not parsed:
            continue
        name, labels, value, ts = parsed

        pod = labels.get("pod", "")
        ns = labels.get("namespace", "")
        if not pod or not ns:
            continue

        key = (pod, ns)

        if name == "kube_pod_info":
            pods[key]["node"] = labels.get("node", "")

        elif name == "kube_pod_owner":
            if value == 1:
                pods[key]["controller_kind"] = labels.get("owner_kind", "")
                pods[key]["controller_name"] = labels.get("owner_name", "")

        elif name == "kube_pod_status_qos_class":
            if value == 1:
                pods[key]["qos_class"] = labels.get("qos_class", "")

        elif name == "kube_pod_created":
            pods[key]["created_time"] = value

        elif name == "kube_pod_status_scheduled_time":
            pods[key]["scheduled_time"] = value

        elif name == "kube_pod_status_initialized_time":
            pods[key]["running_time"] = value

        elif name == "kube_pod_status_ready_time":
            pods[key]["ready_time"] = value

        elif name == "kube_pod_status_phase":
            phase = labels.get("phase", "")
            if value == 1 and phase in ("Succeeded", "Failed"):
                # Garder le premier scrape où la phase est observée
                if phase not in phase_first_scrape[key]:
                    phase_first_scrape[key][phase] = ts

    writer = csv.writer(sys.stdout)
    writer.writerow(
        [
            "pod",
            "namespace",
            "node",
            "controller_kind",
            "controller_name",
            "qos_class",
            "created_time",
            "scheduled_time",
            "running_time",
            "ready_time",
            "succeeded_time",
            "failed_time",
        ]
    )

    for (pod, ns), info in pods.items():
        writer.writerow(
            [
                pod,
                ns,
                info.get("node", ""),
                info.get("controller_kind", ""),
                info.get("controller_name", ""),
                info.get("qos_class", ""),
                info.get("created_time", ""),
                info.get("scheduled_time", ""),
                info.get("running_time", ""),
                info.get("ready_time", ""),
                phase_first_scrape[(pod, ns)].get("Succeeded", ""),
                phase_first_scrape[(pod, ns)].get("Failed", ""),
            ]
        )


if __name__ == "__main__":
    main()

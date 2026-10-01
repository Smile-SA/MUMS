#!/usr/bin/env python3
"""
controller_metadata.py
stdin  : OpenMetrics scrapes (cat <data_dir>/openmetrics/*.om)
stdout : controller_metadata.csv

Key    : (controller_kind, controller_name, namespace)
Columns: controller_kind, controller_name, namespace,
         parent_kind, parent_name, replicas_desired

Every controller is listed, whatever its kind (custom and future ones
included): controllers are found through the generic owner metrics of
kube-state-metrics (kube_pod_owner: the owner of each pod; kube_replicaset_owner
and kube_job_owner: the parent of ReplicaSets and Jobs, e.g. a Deployment or a
CronJob), not through a list of known kinds. Parents are listed too.

replicas_desired is only known for the kinds kube-state-metrics describes
(Deployment, ReplicaSet, StatefulSet, DaemonSet, Job: parallelism); empty for
the others. Values are the last ones observed during the run.
"""

import csv
import re
import sys
from collections import defaultdict

# metric -> (kind, label holding the controller's name)
REPLICAS_DESIRED = {
    "kube_deployment_spec_replicas": ("Deployment", "deployment"),
    "kube_replicaset_spec_replicas": ("ReplicaSet", "replicaset"),
    "kube_statefulset_replicas": ("StatefulSet", "statefulset"),
    "kube_daemonset_status_desired_number_scheduled": ("DaemonSet", "daemonset"),
    "kube_job_spec_parallelism": ("Job", "job_name"),
}
# metric -> (kind, label holding the controller's name): owner of a controller
OWNERS = {
    "kube_replicaset_owner": ("ReplicaSet", "replicaset"),
    "kube_job_owner": ("Job", "job_name"),
}
METRICS = {"kube_pod_owner", *REPLICAS_DESIRED, *OWNERS}
NO_OWNER = ("", "<none>")


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
    controllers = defaultdict(dict)

    for line in sys.stdin:
        parsed = parse_line(line)
        if not parsed:
            continue
        name, labels, value, _ts = parsed
        ns = labels.get("namespace", "")
        if not ns:
            continue

        if name == "kube_pod_owner":
            kind, owner = labels.get("owner_kind", ""), labels.get("owner_name", "")
            if value == 1 and kind not in NO_OWNER and owner not in NO_OWNER:
                controllers[(kind, owner, ns)]  # the owner of a pod is a controller

        elif name in OWNERS:
            kind, label = OWNERS[name]
            ctrl = labels.get(label, "")
            if not ctrl:
                continue
            info = controllers[(kind, ctrl, ns)]
            parent_kind, parent = labels.get("owner_kind", ""), labels.get("owner_name", "")
            if parent_kind not in NO_OWNER and parent not in NO_OWNER:
                info["parent_kind"], info["parent_name"] = parent_kind, parent
                controllers[(parent_kind, parent, ns)]  # the parent is a controller too

        elif name in REPLICAS_DESIRED:
            kind, label = REPLICAS_DESIRED[name]
            ctrl = labels.get(label, "")
            if ctrl:
                controllers[(kind, ctrl, ns)]["replicas_desired"] = value  # last value wins

    writer = csv.writer(sys.stdout)
    writer.writerow(
        ["controller_kind", "controller_name", "namespace", "parent_kind", "parent_name",
         "replicas_desired"]
    )
    for (kind, ctrl, ns), info in sorted(controllers.items()):
        writer.writerow(
            [kind, ctrl, ns, info.get("parent_kind", ""), info.get("parent_name", ""),
             info.get("replicas_desired", "")]
        )


if __name__ == "__main__":
    main()

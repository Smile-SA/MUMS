#!/usr/bin/env python3
"""
controller_timeseries.py
stdin  : metrics.om (OpenMetrics)
stdout : controller_timeseries.csv

Clé    : (timestamp, controller_kind, controller_name, namespace)
Colonnes : timestamp, controller_kind, controller_name, namespace,
           replicas_desired, replicas_ready

Supporte : ReplicaSet, StatefulSet, DaemonSet, Job
"""

import sys
import csv
import re
from collections import defaultdict

# (metric_name) -> (kind, label_key_for_name, field)
METRIC_MAP = {
    'kube_replicaset_spec_replicas':              ('ReplicaSet',  'replicaset',  'desired'),
    'kube_replicaset_status_ready_replicas':       ('ReplicaSet',  'replicaset',  'ready'),
    'kube_statefulset_replicas':                   ('StatefulSet', 'statefulset', 'desired'),
    'kube_statefulset_status_replicas_ready':       ('StatefulSet', 'statefulset', 'ready'),
    'kube_daemonset_status_desired_number_scheduled': ('DaemonSet', 'daemonset',   'desired'),
    'kube_daemonset_status_number_ready':           ('DaemonSet',  'daemonset',   'ready'),
    'kube_job_status_active':                       ('Job',        'job',         'desired'),
    'kube_job_status_succeeded':                    ('Job',        'job',         'ready'),
}

def parse_labels(s):
    return dict(re.findall(r'(\w+)="([^"]*)"', s))

def parse_line(line):
    line = line.strip()
    if not line or line.startswith('#'):
        return None
    m = re.match(r'^(\w+)\{([^}]*)\}\s+([\d.eE+\-]+)\s+(\d+)$', line)
    if not m:
        return None
    name = m.group(1)
    if name not in METRIC_MAP:
        return None
    return name, parse_labels(m.group(2)), float(m.group(3)), int(m.group(4))

def main():
    # data[(kind, ctrl_name, ns, ts)] = {desired, ready}
    data = defaultdict(dict)

    for line in sys.stdin:
        parsed = parse_line(line)
        if not parsed:
            continue
        name, labels, value, ts = parsed

        kind, label_key, field = METRIC_MAP[name]
        ctrl_name = labels.get(label_key, '')
        ns        = labels.get('namespace', '')
        if not ctrl_name or not ns:
            continue

        key = (kind, ctrl_name, ns, ts)
        data[key][field] = value

    writer = csv.writer(sys.stdout)
    writer.writerow([
        'timestamp', 'controller_kind', 'controller_name', 'namespace',
        'replicas_desired', 'replicas_ready',
    ])

    rows = [
        [ts, kind, ctrl_name, ns,
         metrics.get('desired', ''),
         metrics.get('ready', '')]
        for (kind, ctrl_name, ns, ts), metrics in data.items()
    ]
    rows.sort(key=lambda x: x[0])
    writer.writerows(rows)

if __name__ == '__main__':
    main()

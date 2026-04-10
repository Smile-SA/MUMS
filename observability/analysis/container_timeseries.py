#!/usr/bin/env python3
"""
container_timeseries.py
stdin  : metrics.om (OpenMetrics)
stdout : container_timeseries.csv

Colonnes : timestamp, pod, namespace, container, node,
           cpu_usage_rate, memory_working_set_bytes, memory_rss_bytes,
           cpu_throttled_ratio, network_receive_bytes_rate,
           network_transmit_bytes_rate, oom_events_total, restarts_total
"""

import sys
import csv
import re
from collections import defaultdict

METRICS = {
    'container_cpu_usage_seconds_total',
    'container_memory_working_set_bytes',
    'container_memory_rss',
    'container_cpu_cfs_throttled_seconds_total',
    'container_cpu_cfs_periods_total',
    'container_network_receive_bytes_total',
    'container_network_transmit_bytes_total',
    'container_oom_events_total',
    'kube_pod_container_status_restarts_total',
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
    if name not in METRICS:
        return None
    return name, parse_labels(m.group(2)), float(m.group(3)), int(m.group(4))

def get_node(labels):
    return (labels.get('node')
            or labels.get('kubernetes_io_hostname')
            or labels.get('instance', ''))

def main():
    # data[(pod, ns, container, ts)][metric] = value
    data = defaultdict(dict)

    for line in sys.stdin:
        parsed = parse_line(line)
        if not parsed:
            continue
        name, labels, value, ts = parsed

        pod = labels.get('pod', '')
        ns  = labels.get('namespace', '')
        ctr = labels.get('container', '')
        if not pod or not ns or not ctr:
            continue

        key = (pod, ns, ctr, ts)
        data[key]['node'] = get_node(labels)
        data[key][name]   = value

    # Regrouper par (pod, ns, container) et trier par timestamp
    by_container = defaultdict(list)
    for (pod, ns, ctr, ts), metrics in data.items():
        by_container[(pod, ns, ctr)].append((ts, metrics))

    writer = csv.writer(sys.stdout)
    writer.writerow([
        'timestamp', 'pod', 'namespace', 'container', 'node',
        'cpu_usage_rate', 'memory_working_set_bytes', 'memory_rss_bytes',
        'cpu_throttled_ratio', 'network_receive_bytes_rate',
        'network_transmit_bytes_rate', 'oom_events_total', 'restarts_total',
    ])

    for (pod, ns, ctr), points in by_container.items():
        points.sort(key=lambda x: x[0])
        prev_ts  = None
        prev     = {}

        for ts, metrics in points:
            dt = (ts - prev_ts) / 1000.0 if prev_ts is not None else None

            def rate(metric):
                if dt and metric in metrics and metric in prev:
                    return (metrics[metric] - prev[metric]) / dt
                return ''

            # Ratio de throttling : proportion de périodes CFS throttlées
            throttled_ratio = ''
            if dt:
                d_thr = metrics.get('container_cpu_cfs_throttled_seconds_total', 0) \
                      - prev.get('container_cpu_cfs_throttled_seconds_total', 0)
                d_per = metrics.get('container_cpu_cfs_periods_total', 0) \
                      - prev.get('container_cpu_cfs_periods_total', 0)
                if d_per > 0:
                    throttled_ratio = d_thr / d_per

            writer.writerow([
                ts, pod, ns, ctr, metrics.get('node', ''),
                rate('container_cpu_usage_seconds_total'),
                metrics.get('container_memory_working_set_bytes', ''),
                metrics.get('container_memory_rss', ''),
                throttled_ratio,
                rate('container_network_receive_bytes_total'),
                rate('container_network_transmit_bytes_total'),
                metrics.get('container_oom_events_total', ''),
                metrics.get('kube_pod_container_status_restarts_total', ''),
            ])

            prev_ts = ts
            prev    = metrics

if __name__ == '__main__':
    main()

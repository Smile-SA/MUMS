#!/usr/bin/env python3
"""
pod_timeseries.py
Lit trois CSV depuis le disque et agrège les métriques container -> pod.
stdout : pod_timeseries.csv

Usage :
  python3 pod_timeseries.py <container_timeseries.csv> \
                             <container_metadata.csv>   \
                             <pod_metadata.csv>

Règles d'agrégation (par timestamp x pod x namespace) :
  - cpu_usage_rate               : addition
  - memory_working_set_bytes     : addition
  - memory_rss_bytes             : addition
  - network_receive_bytes_rate   : addition
  - network_transmit_bytes_rate  : addition
  - oom_events_total             : addition
  - restarts_total               : addition
  - cpu_throttled_ratio          : moyenne pondérée par cpu_request du container
                                   (si aucun request connu, moyenne simple)

Le champ 'node' est pris depuis pod_metadata (fixe par pod).
"""

import sys
import csv
from collections import defaultdict

def safe_float(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return None

def load_container_metadata(path):
    """Retourne {(pod, namespace, container): row_dict}"""
    meta = {}
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            key = (row['pod'], row['namespace'], row['container'])
            meta[key] = row
    return meta

def load_pod_metadata(path):
    """Retourne {(pod, namespace): row_dict}"""
    meta = {}
    with open(path, newline='') as f:
        for row in csv.DictReader(f):
            key = (row['pod'], row['namespace'])
            meta[key] = row
    return meta

def main():
    if len(sys.argv) != 4:
        print(
            "Usage: pod_timeseries.py <container_timeseries.csv> "
            "<container_metadata.csv> <pod_metadata.csv>",
            file=sys.stderr,
        )
        sys.exit(1)

    container_ts_path   = sys.argv[1]
    container_meta_path = sys.argv[2]
    pod_meta_path       = sys.argv[3]

    container_meta = load_container_metadata(container_meta_path)
    pod_meta       = load_pod_metadata(pod_meta_path)

    # Agrégation : data[(ts, pod, ns)] = dict of accumulators
    agg = defaultdict(lambda: {
        'cpu_usage_rate':             0.0,
        'memory_working_set_bytes':   0.0,
        'memory_rss_bytes':           0.0,
        'network_receive_bytes_rate': 0.0,
        'network_transmit_bytes_rate':0.0,
        'oom_events_total':           0.0,
        'restarts_total':             0.0,
        'throttle_weighted_sum':      0.0,
        'cpu_request_sum':            0.0,
        'throttle_count':             0,   # pour moyenne simple si pas de request
        'has_data':                   False,
    })

    ADDITIVE = [
        'cpu_usage_rate',
        'memory_working_set_bytes',
        'memory_rss_bytes',
        'network_receive_bytes_rate',
        'network_transmit_bytes_rate',
        'oom_events_total',
        'restarts_total',
    ]

    with open(container_ts_path, newline='') as f:
        for row in csv.DictReader(f):
            ts  = row['timestamp']
            pod = row['pod']
            ns  = row['namespace']
            ctr = row['container']
            key = (ts, pod, ns)

            agg[key]['has_data'] = True

            for col in ADDITIVE:
                v = safe_float(row.get(col))
                if v is not None:
                    agg[key][col] += v

            # Throttle : moyenne pondérée par cpu_request
            throttle  = safe_float(row.get('cpu_throttled_ratio'))
            cpu_req   = safe_float(
                container_meta.get((pod, ns, ctr), {}).get('cpu_request')
            )
            if throttle is not None:
                if cpu_req is not None and cpu_req > 0:
                    agg[key]['throttle_weighted_sum'] += throttle * cpu_req
                    agg[key]['cpu_request_sum']       += cpu_req
                else:
                    # Pas de request connu → on accumule pour moyenne simple
                    agg[key]['throttle_weighted_sum'] += throttle
                    agg[key]['throttle_count']        += 1

    writer = csv.writer(sys.stdout)
    writer.writerow([
        'timestamp', 'pod', 'namespace', 'node',
        'cpu_usage_rate', 'memory_working_set_bytes', 'memory_rss_bytes',
        'cpu_throttled_ratio',
        'network_receive_bytes_rate', 'network_transmit_bytes_rate',
        'oom_events_total', 'restarts_total',
    ])

    rows = []
    for (ts, pod, ns), d in agg.items():
        if not d['has_data']:
            continue

        # Résolution du throttle
        if d['cpu_request_sum'] > 0:
            throttle_ratio = d['throttle_weighted_sum'] / d['cpu_request_sum']
        elif d['throttle_count'] > 0:
            throttle_ratio = d['throttle_weighted_sum'] / d['throttle_count']
        else:
            throttle_ratio = ''

        node = pod_meta.get((pod, ns), {}).get('node', '')

        rows.append([
            ts, pod, ns, node,
            d['cpu_usage_rate'],
            d['memory_working_set_bytes'],
            d['memory_rss_bytes'],
            throttle_ratio,
            d['network_receive_bytes_rate'],
            d['network_transmit_bytes_rate'],
            d['oom_events_total'],
            d['restarts_total'],
        ])

    rows.sort(key=lambda x: int(x[0]) if x[0] else 0)
    writer.writerows(rows)

if __name__ == '__main__':
    main()

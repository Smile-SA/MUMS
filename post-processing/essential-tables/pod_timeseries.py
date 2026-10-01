#!/usr/bin/env python3
"""
pod_timeseries.py
Reads three CSVs from disk and aggregates container metrics -> pod.
stdout: pod_timeseries.csv

Usage:
  python3 pod_timeseries.py <container_timeseries.csv> \
                             <container_metadata.csv>   \
                             <pod_metadata.csv>

Aggregation rules (per timestamp x pod x namespace):
  - cpu_usage_rate               : sum
  - memory_working_set_bytes     : sum
  - memory_rss_bytes             : sum
  - network_receive_bytes_rate   : sum
  - network_transmit_bytes_rate  : sum
  - oom_events_total             : sum
  - restarts_total               : sum
  - cpu_throttled_ratio          : weighted average by container cpu_request
                                   (simple average if no request is known)

The 'node' field is taken from pod_metadata (fixed per pod).
"""

import csv
import sys
from collections import defaultdict


def safe_float(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def load_container_metadata(path):
    """Returns {(pod, namespace, container): row_dict}"""
    meta = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            key = (row["pod"], row["namespace"], row["container"])
            meta[key] = row
    return meta


def load_pod_metadata(path):
    """Returns {(pod, namespace): row_dict}"""
    meta = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            key = (row["pod"], row["namespace"])
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

    container_ts_path = sys.argv[1]
    container_meta_path = sys.argv[2]
    pod_meta_path = sys.argv[3]

    container_meta = load_container_metadata(container_meta_path)
    pod_meta = load_pod_metadata(pod_meta_path)

    # Aggregation: data[(ts, pod, ns)] = dict of accumulators
    agg = defaultdict(
        lambda: {
            "cpu_usage_rate": 0.0,
            "memory_working_set_bytes": 0.0,
            "memory_rss_bytes": 0.0,
            "network_receive_bytes_rate": 0.0,
            "network_transmit_bytes_rate": 0.0,
            "oom_events_total": 0.0,
            "restarts_total": 0.0,
            "throttle_weighted_sum": 0.0,
            "cpu_request_sum": 0.0,
            "throttle_count": 0,  # for simple average when cpu_request is unknown
            "has_data": False,
        }
    )

    ADDITIVE = [
        "cpu_usage_rate",
        "memory_working_set_bytes",
        "memory_rss_bytes",
        "network_receive_bytes_rate",
        "network_transmit_bytes_rate",
        "oom_events_total",
        "restarts_total",
    ]

    with open(container_ts_path, newline="") as f:
        for row in csv.DictReader(f):
            ts = row["timestamp"]
            pod = row["pod"]
            ns = row["namespace"]
            ctr = row["container"]
            key = (ts, pod, ns)

            agg[key]["has_data"] = True

            for col in ADDITIVE:
                v = safe_float(row.get(col))
                if v is not None:
                    agg[key][col] += v
                    agg[key]["seen_" + col] = 1  # at least one container had a value

            # Throttle: weighted average by cpu_request
            throttle = safe_float(row.get("cpu_throttled_ratio"))
            cpu_req = safe_float(container_meta.get((pod, ns, ctr), {}).get("cpu_request"))
            if throttle is not None:
                if cpu_req is not None and cpu_req > 0:
                    agg[key]["throttle_weighted_sum"] += throttle * cpu_req
                    agg[key]["cpu_request_sum"] += cpu_req
                else:
                    # No known request → accumulate for simple average
                    agg[key]["throttle_weighted_sum"] += throttle
                    agg[key]["throttle_count"] += 1

    writer = csv.writer(sys.stdout)
    writer.writerow(
        [
            "timestamp",
            "pod",
            "namespace",
            "node",
            "cpu_usage_rate",
            "memory_working_set_bytes",
            "memory_rss_bytes",
            "cpu_throttled_ratio",
            "network_receive_bytes_rate",
            "network_transmit_bytes_rate",
            "oom_events_total",
            "restarts_total",
        ]
    )

    rows = []
    for (ts, pod, ns), d in agg.items():
        if not d["has_data"]:
            continue

        # Resolve throttle ratio
        if d["cpu_request_sum"] > 0:
            throttle_ratio = d["throttle_weighted_sum"] / d["cpu_request_sum"]
        elif d["throttle_count"] > 0:
            throttle_ratio = d["throttle_weighted_sum"] / d["throttle_count"]
        else:
            throttle_ratio = ""

        node = pod_meta.get((pod, ns), {}).get("node", "")

        def total(col, d=d):
            # Empty (not 0) when no container of the pod had a value at this time.
            return d[col] if d.get("seen_" + col) else ""

        rows.append(
            [
                ts,
                pod,
                ns,
                node,
                total("cpu_usage_rate"),
                total("memory_working_set_bytes"),
                total("memory_rss_bytes"),
                throttle_ratio,
                total("network_receive_bytes_rate"),
                total("network_transmit_bytes_rate"),
                total("oom_events_total"),
                total("restarts_total"),
            ]
        )

    rows.sort(key=lambda x: float(x[0]) if x[0] else 0.0)
    writer.writerows(rows)


if __name__ == "__main__":
    main()

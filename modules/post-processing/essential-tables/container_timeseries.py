#!/usr/bin/env python3
"""
container_timeseries.py
stdin  : OpenMetrics scrapes (cat <data_dir>/openmetrics/*.om)
stdout : container_timeseries.csv

Columns: timestamp, pod, namespace, container, node,
         cpu_usage_rate, memory_working_set_bytes, memory_rss_bytes,
         cpu_throttled_ratio, network_receive_bytes_rate,
         network_transmit_bytes_rate, oom_events_total, restarts_total
"""

import csv
import re
import sys
from collections import defaultdict

METRICS = {
    "container_cpu_usage_seconds_total",
    "container_memory_working_set_bytes",
    "container_memory_rss",
    "container_cpu_cfs_throttled_seconds_total",
    "container_cpu_cfs_periods_total",
    "container_network_receive_bytes_total",
    "container_network_transmit_bytes_total",
    "container_oom_events_total",
    "kube_pod_container_status_restarts_total",
    "container_start_time_seconds",
}



def seconds(ms):
    """Prometheus sample timestamp (Unix milliseconds) -> Unix seconds."""
    return f"{ms / 1000:.3f}"


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
    # data[(pod, ns, container, ts)][metric] = value
    data = defaultdict(dict)

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

        key = (pod, ns, ctr, ts)
        data[key]["node"] = get_node(labels)
        data[key][name] = value

    # Regrouper par (pod, ns, container) et trier par timestamp
    by_container = defaultdict(list)
    for (pod, ns, ctr, ts), metrics in data.items():
        by_container[(pod, ns, ctr)].append((ts, metrics))

    writer = csv.writer(sys.stdout)
    writer.writerow(
        [
            "timestamp",
            "pod",
            "namespace",
            "container",
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

    for (pod, ns, ctr), points in by_container.items():
        points.sort(key=lambda x: x[0])
        # Last sample of each counter: (value, timestamp in ms). Kept per metric,
        # since metrics from different sources (cAdvisor, kube-state-metrics)
        # do not share timestamps.
        last = {}
        # Every start time reported for this container (Unix seconds): one per
        # (re)start. Its samples carry their own timestamps, possibly later than
        # the first usage samples, so all of them are gathered first.
        starts = sorted(
            {m["container_start_time_seconds"] for _, m in points
             if "container_start_time_seconds" in m}
        )

        for ts, metrics in points:
            # The start that applies to this sample: the latest one before it.
            start = max((st for st in starts if st * 1000 <= ts), default=None)

            def delta(metric, metrics=metrics, ts=ts, start=start, last=last):
                """(increase, elapsed seconds) of a counter since its previous
                sample. After a creation or a restart, the counter starts from
                0 at the container start: its value is then the increase since
                that start (an extra point for the first sample, and a correct
                value instead of a negative one after a restart)."""
                if metric not in metrics:
                    return None
                current = metrics[metric]
                previous = last.get(metric)
                restarted = previous is not None and (
                    current < previous[0]
                    or (start is not None and start * 1000 > previous[1])
                )
                if previous is not None and not restarted:
                    return current - previous[0], (ts - previous[1]) / 1000.0
                if start is not None and ts / 1000.0 > start:
                    return current, ts / 1000.0 - start
                return None

            def rate(metric):
                d = delta(metric)
                return d[0] / d[1] if d and d[1] > 0 else ""

            cpu_rate = rate("container_cpu_usage_seconds_total")
            rx_rate = rate("container_network_receive_bytes_total")
            tx_rate = rate("container_network_transmit_bytes_total")

            # Throttle ratio: fraction of CFS periods that were throttled.
            throttled_ratio = ""
            d_thr = delta("container_cpu_cfs_throttled_seconds_total")
            d_per = delta("container_cpu_cfs_periods_total")
            if d_thr and d_per and d_per[0] > 0:
                throttled_ratio = d_thr[0] / d_per[0]

            for metric in (
                "container_cpu_usage_seconds_total",
                "container_network_receive_bytes_total",
                "container_network_transmit_bytes_total",
                "container_cpu_cfs_throttled_seconds_total",
                "container_cpu_cfs_periods_total",
            ):
                if metric in metrics:
                    last[metric] = (metrics[metric], ts)

            if not any(m in metrics for m in METRICS - {"container_start_time_seconds"}):
                continue

            writer.writerow(
                [
                    seconds(ts),
                    pod,
                    ns,
                    ctr,
                    metrics.get("node", ""),
                    cpu_rate,
                    metrics.get("container_memory_working_set_bytes", ""),
                    metrics.get("container_memory_rss", ""),
                    throttled_ratio,
                    rx_rate,
                    tx_rate,
                    metrics.get("container_oom_events_total", ""),
                    metrics.get("kube_pod_container_status_restarts_total", ""),
                ]
            )


if __name__ == "__main__":
    main()

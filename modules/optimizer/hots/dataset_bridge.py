"""Convert a mums run's refined datasets into HOTS's
`FileConnector` input shape, for the "offline dataset -> HOTS only" scenario
(no live cluster, no Kafka -- see run.sh in this directory for the live path).

Source: `datasets/pod_timeseries` + `datasets/pod_metadata` (pod granularity
-- no container->pod aggregation needed, unlike `container_timeseries`) and
`datasets/node_metadata` (node CPU capacity).

Output, in `<output_dir>`:
  container_usage.csv  timestamp,pod,node,<metric>  (one row per tick per pod)
  node_meta.csv         node,<metric>                (one row per node)

Usage:
  python3 optimizers/hots/dataset_bridge.py <run_dir> <output_dir>
      [--namespace online-boutique] [--metric cpu_usage_rate]
      [--exclude-controller-kind DaemonSet [...]]
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

DEFAULT_NAMESPACE = "online-boutique"
DEFAULT_METRIC = "cpu_usage_rate"
DEFAULT_EXCLUDED_CONTROLLER_KINDS = ("DaemonSet",)


def _read_csv_rows(table_dir: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if not table_dir.is_dir():
        return rows
    for path in sorted(table_dir.glob("*.csv")):
        with path.open(newline="", encoding="utf-8") as stream:
            rows.extend(csv.DictReader(stream))
    return rows


def _schedulable_pods(
    run_dir: Path, namespace: str, excluded_controller_kinds: set[str]
) -> set[str]:
    """Pods in `namespace` not owned by an excluded controller kind (e.g.
    DaemonSets, which run on every node and can't meaningfully be
    rescheduled by a placement optimizer)."""
    rows = _read_csv_rows(run_dir / "datasets" / "pod_metadata")
    return {
        row["pod"]
        for row in rows
        if row.get("namespace") == namespace
        and row.get("controller_kind", "") not in excluded_controller_kinds
        and row.get("pod")
    }


def convert(
    run_dir: Path,
    output_dir: Path,
    *,
    namespace: str = DEFAULT_NAMESPACE,
    metric: str = DEFAULT_METRIC,
    excluded_controller_kinds: set[str] | None = None,
) -> tuple[Path, Path]:
    """Write container_usage.csv + node_meta.csv into output_dir. Returns
    their paths."""
    excluded = (
        set(excluded_controller_kinds)
        if excluded_controller_kinds is not None
        else set(DEFAULT_EXCLUDED_CONTROLLER_KINDS)
    )
    keep_pods = _schedulable_pods(run_dir, namespace, excluded)

    by_pod: dict[str, list[dict[str, str]]] = {}
    for row in _read_csv_rows(run_dir / "datasets" / "pod_timeseries"):
        pod = row.get("pod")
        if pod in keep_pods:
            by_pod.setdefault(pod, []).append(row)

    # One row per (tick, pod), forward-filling short gaps in `metric` per pod
    # so HOTS's per-tick windowing sees a dense series rather than the sparse
    # scrape data that's normal in a real run (missed scrapes, metrics that
    # only appear once cAdvisor has a second sample, etc).
    usage_rows: list[tuple[int, str, str, str]] = []
    for pod, rows in by_pod.items():
        rows.sort(key=lambda r: int(r["timestamp"]))
        last_value: str | None = None
        last_node: str | None = None
        for row in rows:
            value = row.get(metric) or None
            node = row.get("node") or None
            if value is not None:
                last_value = value
            if node is not None:
                last_node = node
            if last_value is None or last_node is None:
                continue  # no data yet for this pod -- nothing to forward-fill from
            usage_rows.append((int(row["timestamp"]), pod, last_node, last_value))

    # HOTS's FileConnector assumes the CSV is sorted ascending by tick_field.
    usage_rows.sort(key=lambda r: (r[0], r[1]))

    output_dir.mkdir(parents=True, exist_ok=True)

    usage_path = output_dir / "container_usage.csv"
    with usage_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["timestamp", "pod", "node", metric])
        writer.writerows(usage_rows)

    node_meta_path = output_dir / "node_meta.csv"
    with node_meta_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["node", metric])
        for row in _read_csv_rows(run_dir / "datasets" / "node_metadata"):
            if row.get("node") and row.get("cpu_allocatable"):
                writer.writerow([row["node"], row["cpu_allocatable"]])

    return usage_path, node_meta_path


def hots_data_config_snippet(metric: str) -> dict[str, object]:
    """The HOTS `data:` config section matching convert()'s output columns."""
    return {
        "tick_field": "timestamp",
        "individual_field": "pod",
        "host_field": "node",
        "metrics": [metric],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--namespace", default=DEFAULT_NAMESPACE)
    parser.add_argument("--metric", default=DEFAULT_METRIC)
    parser.add_argument(
        "--exclude-controller-kind",
        dest="excluded_controller_kinds",
        action="append",
        default=None,
        help=f"Repeatable. Default: {', '.join(DEFAULT_EXCLUDED_CONTROLLER_KINDS)}",
    )
    args = parser.parse_args()

    excluded = (
        set(args.excluded_controller_kinds) if args.excluded_controller_kinds else None
    )
    usage_path, node_meta_path = convert(
        args.run_dir,
        args.output_dir,
        namespace=args.namespace,
        metric=args.metric,
        excluded_controller_kinds=excluded,
    )

    print(usage_path)
    print(node_meta_path)
    print("Matching HOTS data: config section:")
    print(hots_data_config_snippet(args.metric))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

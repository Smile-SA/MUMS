#!/usr/bin/env python3
"""Render a HOTS JSON config for a live benchmark-platform run.

Queries the cluster for per-node CPU allocatable capacity (used by HOTS's
Kafka connector as `connector.parameters.node_capacities`) and writes a
complete HOTS config to --output. See hots/config/sample_config_kafka.json
in the HOTS repo for the config shape this is modeled on.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def parse_cpu_quantity(value: str) -> float:
    """Parse a Kubernetes CPU quantity ("2", "500m", "2000m") into cores."""
    value = value.strip()
    if value.endswith("m"):
        return float(value[:-1]) / 1000.0
    return float(value)


def node_capacities(kubeconfig: str) -> dict[str, float]:
    """Per-node allocatable CPU (cores), keyed by node name."""
    result = subprocess.run(
        ["kubectl", "--kubeconfig", kubeconfig, "get", "nodes", "-o", "json"],
        capture_output=True,
        text=True,
        check=True,
    )
    nodes = json.loads(result.stdout).get("items", [])
    capacities: dict[str, float] = {}
    for node in nodes:
        name = node.get("metadata", {}).get("name")
        cpu = node.get("status", {}).get("allocatable", {}).get("cpu")
        if name and cpu:
            capacities[name] = parse_cpu_quantity(cpu)
    return capacities


def build_config(
    *,
    kafka_port: int,
    metric: str,
    nb_clusters: int,
    tick_seconds: int,
    topic_data: str,
    topic_moves: str,
    capacities: dict[str, float],
    results_dir: Path,
) -> dict[str, Any]:
    bootstrap = f"localhost:{kafka_port}"
    return {
        "time_limit": None,
        "data": {
            "tick_field": "timestamp",
            "individual_field": "pod",
            "host_field": "node",
            "metrics": [metric],
        },
        "clustering": {
            "method": "kmeans",
            "nb_clusters": nb_clusters,
            "parameters": {"nb_clusters": nb_clusters},
        },
        "optimization": {
            "backend": "pyomo",
            "parameters": {"solver": "glpk", "verbose": 0},
        },
        "problem": {
            "type": "placement",
            "parameters": {"initial_placement": False, "tol": 0.1, "tol_move": 0.2},
        },
        "connector": {
            "type": "kafka",
            "parameters": {
                "tick_field": "timestamp",
                "individual_field": "pod",
                "host_field": "node",
                "metrics": [metric],
                # sep_time is compared directly against real Prometheus epoch
                # timestamps (see KafkaConnector._poll_records/load_initial), so
                # any small placeholder is trivially satisfied by the first real
                # tick observed -- bootstrap completes on the first batch.
                "sep_time": 30,
                "tick_increment": tick_seconds,
                "window_duration": 3,
                "bootstrap.servers": bootstrap,
                "topic_data": topic_data,
                "topic_moves": topic_moves,
                "consumer_conf": {
                    "bootstrap.servers": bootstrap,
                    "group.id": "hots",
                    "auto.offset.reset": "earliest",
                },
                "batch_size": 1,
                # Must exceed the connector's publish cadence (tick_seconds):
                # load_next() does a *single* poll() of this duration and
                # treats an empty result as "data source exhausted" (breaks
                # the streaming loop, see KafkaConnector._poll_records with
                # stop_at_tick=None) -- 1.0s (HOTS's own sample config value,
                # tuned for a dense test fixture) is far shorter than a live
                # 10s telemetry cadence and ends the run after one empty poll.
                # A generous multiple (not just a fixed margin) is used
                # because this is a hard cutoff, not a retry budget: any
                # single publish tick slower than poll_timeout (a slow
                # Prometheus/K8s API call, a GC pause) ends the run early.
                # This narrows but does not eliminate that window -- see the
                # "known limitation" note in this module's README.md.
                "poll_timeout": float(tick_seconds) * 3 + 5.0,
                "bootstrap_timeout_seconds": 120,
                "node_capacities": capacities,
            },
        },
        "logging": {
            "level": "INFO",
            "filename": str(results_dir / "hots.log"),
            "fmt": "%(asctime)s %(levelname)s: %(message)s",
        },
        "reporting": {
            "results_folder": str(results_dir),
            "metrics_file": str(results_dir / "hots-metrics.csv"),
            "plots_folder": str(results_dir / "plots"),
        },
        "visualization": {"enabled": False},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_path", help="Where to write the rendered HOTS config JSON.")
    parser.add_argument("--kubeconfig", required=True)
    parser.add_argument("--kafka-port", type=int, required=True)
    parser.add_argument("--metric", required=True)
    parser.add_argument("--nb-clusters", type=int, required=True)
    parser.add_argument("--tick-seconds", type=int, required=True)
    parser.add_argument("--topic-data", required=True)
    parser.add_argument("--topic-moves", required=True)
    parser.add_argument("--results-dir", required=True)
    args = parser.parse_args()

    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    capacities = node_capacities(args.kubeconfig)
    if not capacities:
        raise SystemExit("ERROR: could not determine node CPU capacities from the cluster.")

    config = build_config(
        kafka_port=args.kafka_port,
        metric=args.metric,
        nb_clusters=args.nb_clusters,
        tick_seconds=args.tick_seconds,
        topic_data=args.topic_data,
        topic_moves=args.topic_moves,
        capacities=capacities,
        results_dir=results_dir,
    )

    Path(args.output_path).write_text(json.dumps(config, indent=2), encoding="utf-8")
    print(f"Rendered HOTS config: {args.output_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

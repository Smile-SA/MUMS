from __future__ import annotations

import argparse
import csv
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

DATASET_FORMAT_VERSION = 1

TABLE_FAMILIES = [
    "container_timeseries",
    "container_metadata",
    "pod_timeseries",
    "pod_metadata",
    "node_timeseries",
    "node_metadata",
    "controller_timeseries",
    "controller_metadata",
]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream)
    return data if isinstance(data, dict) else {}


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_bool(value: str | None) -> bool:
    return str(value or "").lower() in {"1", "true", "yes", "y"}


def _parse_int(value: str | None) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(value))
    except ValueError:
        return None


def validate_run_dir(run_dir: Path) -> None:
    required = [
        run_dir / "manifest.yaml",
        run_dir / "config.yaml",
        run_dir / "metrics",
    ]

    missing = [path for path in required if not path.exists()]
    if missing:
        missing_text = ", ".join(_relative(path, run_dir) for path in missing)
        raise FileNotFoundError(
            f"Invalid benchmark run directory: {run_dir}. Missing: {missing_text}"
        )


def _read_scrapes(scrapes_path: Path) -> list[dict[str, Any]]:
    if not scrapes_path.exists():
        return []

    rows: list[dict[str, Any]] = []
    with scrapes_path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        for row in reader:
            started_at = _parse_datetime(row.get("started_at"))
            ended_at = _parse_datetime(row.get("ended_at"))
            rows.append(
                {
                    "scrape_index": _parse_int(row.get("scrape_index")),
                    "started_at": row.get("started_at") or "",
                    "ended_at": row.get("ended_at") or "",
                    "started_at_dt": started_at,
                    "ended_at_dt": ended_at,
                    "success": _parse_bool(row.get("success")),
                    "http_status": row.get("http_status") or "",
                    "bytes_written": _parse_int(row.get("bytes_written")) or 0,
                    "error": row.get("error") or "",
                }
            )

    rows.sort(key=lambda row: row["started_at_dt"] or datetime.min.replace(tzinfo=UTC))
    return rows


def _find_event_time(manifest: dict[str, Any], event_type: str) -> datetime | None:
    events = manifest.get("events", [])
    if not isinstance(events, list):
        return None

    for event in events:
        if isinstance(event, dict) and event.get("type") == event_type:
            return _parse_datetime(str(event.get("time", "")))
    return None


def _estimate_expected_scrapes(
    start: datetime | None,
    end: datetime | None,
    frequency_seconds: int | None,
) -> int | None:
    if start is None or end is None or not frequency_seconds or end < start:
        return None
    return int((end - start).total_seconds() // frequency_seconds) + 1


def _build_collection_quality(
    *,
    manifest: dict[str, Any],
    config: dict[str, Any],
    scrapes_path: Path,
) -> dict[str, Any]:
    observability = config.get("observability", {})
    frequency_seconds = None
    if isinstance(observability, dict) and "frequency_seconds" in observability:
        frequency_seconds = _parse_int(str(observability["frequency_seconds"]))

    rows = _read_scrapes(scrapes_path)

    if not rows:
        return {
            "scrape_frequency_seconds": frequency_seconds,
            "expected_scrapes": None,
            "recorded_scrapes": 0,
            "successful_scrapes": 0,
            "failed_scrapes": 0,
            "empty_scrapes": 0,
            "success_ratio": None,
            "first_scrape_at": None,
            "last_scrape_at": None,
            "missing_or_incomplete_periods": [
                {
                    "reason": "missing_scrape_metadata",
                    "details": "metrics/scrapes.csv is missing or empty.",
                }
            ],
        }

    successful = [row for row in rows if row["success"]]
    failed = [row for row in rows if not row["success"]]
    empty = [row for row in rows if row["success"] and row["bytes_written"] <= 0]

    first_scrape = rows[0]["started_at_dt"]
    last_scrape = rows[-1]["started_at_dt"]

    observability_start = _find_event_time(manifest, "observability.start")
    observability_stop = _find_event_time(manifest, "observability.stop")
    run_end = _parse_datetime(str(manifest.get("ended_at", "")))
    collection_end = observability_stop or run_end or last_scrape

    expected = _estimate_expected_scrapes(
        observability_start or first_scrape,
        collection_end,
        frequency_seconds,
    )

    periods: list[dict[str, Any]] = []

    for row in failed:
        periods.append(
            {
                "reason": "failed_scrape",
                "started_at": row["started_at"],
                "ended_at": row["ended_at"],
                "http_status": row["http_status"],
                "error": row["error"],
            }
        )

    for row in empty:
        periods.append(
            {
                "reason": "empty_scrape",
                "started_at": row["started_at"],
                "ended_at": row["ended_at"],
                "http_status": row["http_status"],
                "bytes_written": row["bytes_written"],
            }
        )

    if frequency_seconds:
        tolerance = frequency_seconds * 1.5

        if observability_start and first_scrape:
            initial_gap = (first_scrape - observability_start).total_seconds()
            if initial_gap > tolerance:
                periods.append(
                    {
                        "reason": "initial_collection_gap",
                        "started_at": observability_start.isoformat(),
                        "ended_at": first_scrape.isoformat(),
                        "gap_seconds": round(initial_gap, 3),
                    }
                )

        for previous, current in zip(rows, rows[1:], strict=False):
            previous_start = previous["started_at_dt"]
            current_start = current["started_at_dt"]
            if previous_start is None or current_start is None:
                continue

            gap = (current_start - previous_start).total_seconds()
            if gap > tolerance:
                periods.append(
                    {
                        "reason": "large_gap_between_scrapes",
                        "started_at": (
                            previous_start + timedelta(seconds=frequency_seconds)
                        ).isoformat(),
                        "ended_at": current_start.isoformat(),
                        "gap_seconds": round(gap, 3),
                    }
                )

        if collection_end and last_scrape:
            final_gap = (collection_end - last_scrape).total_seconds()
            if final_gap > tolerance:
                periods.append(
                    {
                        "reason": "final_collection_gap",
                        "started_at": last_scrape.isoformat(),
                        "ended_at": collection_end.isoformat(),
                        "gap_seconds": round(final_gap, 3),
                    }
                )

    recorded = len(rows)
    success_ratio = len(successful) / recorded if recorded else None

    return {
        "scrape_frequency_seconds": frequency_seconds,
        "expected_scrapes": expected,
        "recorded_scrapes": recorded,
        "successful_scrapes": len(successful),
        "failed_scrapes": len(failed),
        "empty_scrapes": len(empty),
        "success_ratio": round(success_ratio, 6) if success_ratio is not None else None,
        "first_scrape_at": first_scrape.isoformat() if first_scrape else None,
        "last_scrape_at": last_scrape.isoformat() if last_scrape else None,
        "missing_or_incomplete_periods": periods,
    }


def _list_tables(run_dir: Path) -> dict[str, list[str]]:
    datasets_dir = run_dir / "datasets"
    tables: dict[str, list[str]] = {}

    for table in TABLE_FAMILIES:
        table_dir = datasets_dir / table
        if not table_dir.exists():
            continue

        files = sorted(path for path in table_dir.glob("*.csv") if path.is_file())
        if files:
            tables[table] = [_relative(path, run_dir) for path in files]

    return tables


def _extract_container_images(run_dir: Path) -> list[dict[str, str]]:
    pods_path = run_dir / "kubernetes" / "pods.yaml"
    pods = _load_yaml(pods_path)

    images: dict[tuple[str, str, str, str], dict[str, str]] = {}

    for item in pods.get("items", []) if isinstance(pods.get("items"), list) else []:
        if not isinstance(item, dict):
            continue

        metadata = item.get("metadata", {})
        spec = item.get("spec", {})
        status = item.get("status", {})

        namespace = str(metadata.get("namespace", ""))
        pod = str(metadata.get("name", ""))

        status_by_name: dict[str, dict[str, Any]] = {}
        for status_field in (
            "initContainerStatuses",
            "containerStatuses",
            "ephemeralContainerStatuses",
        ):
            statuses = status.get(status_field, [])
            if isinstance(statuses, list):
                for container_status in statuses:
                    if isinstance(container_status, dict):
                        status_by_name[str(container_status.get("name", ""))] = container_status

        for spec_field in ("initContainers", "containers", "ephemeralContainers"):
            containers = spec.get(spec_field, [])
            if not isinstance(containers, list):
                continue

            for container in containers:
                if not isinstance(container, dict):
                    continue

                name = str(container.get("name", ""))
                image = str(container.get("image", ""))
                image_id = str(status_by_name.get(name, {}).get("imageID", ""))

                key = (namespace, pod, name, image)
                images[key] = {
                    "namespace": namespace,
                    "pod": pod,
                    "container": name,
                    "image": image,
                    "image_id": image_id,
                }

    return sorted(
        images.values(), key=lambda item: (item["namespace"], item["pod"], item["container"])
    )


def _extract_chart_references(run_dir: Path) -> list[dict[str, str]]:
    references: list[dict[str, str]] = []

    for log_name in ("stack.log", "observability-start.log", "environment-create.log"):
        log_path = run_dir / "logs" / log_name
        if not log_path.exists():
            continue

        for line in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("Chart:"):
                references.append(
                    {
                        "source_log": _relative(log_path, run_dir),
                        "chart": stripped.split("Chart:", 1)[1].strip(),
                    }
                )

    return references


def _build_provenance(
    run_dir: Path, manifest: dict[str, Any], config: dict[str, Any]
) -> dict[str, Any]:
    kubernetes = run_dir / "kubernetes"

    kubernetes_artifacts = {
        name: _relative(kubernetes / name, run_dir)
        for name in [
            "nodes.yaml",
            "pods.yaml",
            "services.yaml",
            "deployments.yaml",
            "events.txt",
        ]
        if (kubernetes / name).exists()
    }

    return {
        "run_id": manifest.get("run_id"),
        "scenario": manifest.get("scenario") or config.get("scenario", {}).get("name"),
        "seed": manifest.get("seed") or config.get("scenario", {}).get("seed"),
        "environment": manifest.get("environment") or config.get("environment"),
        "optimizer": manifest.get("optimizer") or config.get("optimizer"),
        "stack": config.get("stack"),
        "observability": config.get("observability"),
        "traffic": config.get("traffic"),
        "kubernetes_artifacts": kubernetes_artifacts,
        "chart_references": _extract_chart_references(run_dir),
        "container_images": _extract_container_images(run_dir),
    }


def build_metadata(run_dir: Path) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    validate_run_dir(run_dir)

    manifest_path = run_dir / "manifest.yaml"
    config_path = run_dir / "config.yaml"
    metrics_dir = run_dir / "metrics"
    raw_metrics_path = metrics_dir / "metrics.om"
    scrapes_path = metrics_dir / "scrapes.csv"

    manifest = _load_yaml(manifest_path)
    config = _load_yaml(config_path)

    tables = _list_tables(run_dir)

    return {
        "dataset_format_version": DATASET_FORMAT_VERSION,
        "generated_at": utc_now(),
        "run": {
            "manifest": _relative(manifest_path, run_dir),
            "config": _relative(config_path, run_dir),
            "run_id": manifest.get("run_id"),
            "scenario": manifest.get("scenario"),
            "seed": manifest.get("seed"),
            "status": manifest.get("status"),
            "started_at": manifest.get("started_at"),
            "ended_at": manifest.get("ended_at"),
        },
        "source_artifacts": {
            "raw_metrics": _relative(raw_metrics_path, run_dir)
            if raw_metrics_path.exists()
            else None,
            "scrape_metadata": _relative(scrapes_path, run_dir) if scrapes_path.exists() else None,
        },
        "collection_quality": _build_collection_quality(
            manifest=manifest,
            config=config,
            scrapes_path=scrapes_path,
        ),
        "generated_table_families": sorted(tables.keys()),
        "tables": tables,
        "schema_documentation": {
            "overview": "docs/datasets.md",
            "refined_csv": "docs/schemas/refined-csv.md",
        },
        "provenance": _build_provenance(run_dir, manifest, config),
    }


def write_metadata(run_dir: Path) -> Path:
    run_dir = run_dir.resolve()
    metadata = build_metadata(run_dir)

    output = run_dir / "post-processing" / "dataset-metadata.yaml"
    output.parent.mkdir(parents=True, exist_ok=True)

    with output.open("w", encoding="utf-8") as stream:
        yaml.safe_dump(metadata, stream, sort_keys=False, allow_unicode=True)

    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate dataset metadata for a benchmark run.")
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()

    output = write_metadata(args.run_dir)
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


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


def build_metadata(run_dir: Path) -> dict[str, Any]:
    datasets_dir = run_dir / "datasets"
    metrics_dir = run_dir / "metrics"

    tables: dict[str, list[str]] = {}
    for table in TABLE_FAMILIES:
        table_dir = datasets_dir / table
        if table_dir.exists():
            tables[table] = sorted(str(path.relative_to(run_dir)) for path in table_dir.glob("*.csv"))

    return {
        "dataset_format_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_manifest": "manifest.yaml",
        "raw_metrics": str((metrics_dir / "metrics.om").relative_to(run_dir)),
        "scrape_metadata": str((metrics_dir / "scrapes.csv").relative_to(run_dir))
        if (metrics_dir / "scrapes.csv").exists()
        else None,
        "tables": tables,
        "schema_documentation": "docs/datasets.md",
    }


def write_metadata(run_dir: Path) -> Path:
    metadata = build_metadata(run_dir)
    output = run_dir / "datasets" / "dataset-metadata.yaml"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as stream:
        yaml.safe_dump(metadata, stream, sort_keys=False)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir")
    args = parser.parse_args()

    output = write_metadata(Path(args.run_dir).resolve())
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

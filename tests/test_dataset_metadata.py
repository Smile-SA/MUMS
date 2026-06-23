from pathlib import Path

import yaml

from benchmark_platform.datasets.metadata import build_metadata, write_metadata


def test_dataset_metadata_reports_quality_and_tables(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "metrics").mkdir(parents=True)
    (run_dir / "datasets" / "container_timeseries").mkdir(parents=True)
    (run_dir / "kubernetes").mkdir(parents=True)

    (run_dir / "manifest.yaml").write_text(
        """
run_id: test-run
scenario: test
seed: 42
status: completed
started_at: "2026-01-01T00:00:00+00:00"
ended_at: "2026-01-01T00:01:00+00:00"
events:
  - time: "2026-01-01T00:00:00+00:00"
    type: observability.start
  - time: "2026-01-01T00:01:00+00:00"
    type: observability.stop
environment:
  type: kind
  node_image: kindest/node:v1.34.0
""",
        encoding="utf-8",
    )

    (run_dir / "config.yaml").write_text(
        """
version: 1
scenario:
  name: test
  seed: 42
  duration_seconds: 60
environment:
  type: kind
  workers:
    count: 1
    cpu: "1"
    memory: "1Gi"
stack:
  type: online-boutique
observability:
  type: prometheus
  frequency_seconds: 15
traffic:
  type: locust
  shape: journee_type
  cycle_minutes: 1
optimizer:
  type: baseline
output:
  root_directory: output/runs
""",
        encoding="utf-8",
    )

    (run_dir / "metrics" / "metrics.om").write_text("# test\n", encoding="utf-8")
    (run_dir / "metrics" / "scrapes.csv").write_text(
        "\n".join(
            [
                "scrape_index,started_at,ended_at,success,http_status,bytes_written,error",
                "1,2026-01-01T00:00:00+00:00,2026-01-01T00:00:01+00:00,true,200,100,",
                "2,2026-01-01T00:00:15+00:00,2026-01-01T00:00:16+00:00,false,500,0,boom",
                "3,2026-01-01T00:00:45+00:00,2026-01-01T00:00:46+00:00,true,200,100,",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    (run_dir / "datasets" / "container_timeseries" / "container_timeseries_1.csv").write_text(
        "timestamp,pod,namespace,container,node,cpu_usage_rate\n",
        encoding="utf-8",
    )

    (run_dir / "kubernetes" / "pods.yaml").write_text(
        """
items:
  - metadata:
      namespace: default
      name: pod-a
    spec:
      containers:
        - name: frontend
          image: example/frontend:v1
    status:
      containerStatuses:
        - name: frontend
          imageID: docker-pullable://example/frontend@sha256:abc
""",
        encoding="utf-8",
    )

    metadata = build_metadata(run_dir)

    assert metadata["dataset_format_version"] == 1
    assert metadata["source_artifacts"]["raw_metrics"] == "metrics/metrics.om"
    assert metadata["source_artifacts"]["scrape_metadata"] == "metrics/scrapes.csv"
    assert metadata["collection_quality"]["scrape_frequency_seconds"] == 15
    assert metadata["collection_quality"]["recorded_scrapes"] == 3
    assert metadata["collection_quality"]["successful_scrapes"] == 2
    assert metadata["collection_quality"]["failed_scrapes"] == 1
    assert metadata["generated_table_families"] == ["container_timeseries"]
    assert metadata["provenance"]["container_images"][0]["image"] == "example/frontend:v1"

    reasons = {
        period["reason"]
        for period in metadata["collection_quality"]["missing_or_incomplete_periods"]
    }
    assert "failed_scrape" in reasons
    assert "large_gap_between_scrapes" in reasons


def test_write_metadata_creates_yaml(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    (run_dir / "metrics").mkdir(parents=True)
    (run_dir / "datasets").mkdir()
    (run_dir / "manifest.yaml").write_text("run_id: test\n", encoding="utf-8")
    (run_dir / "config.yaml").write_text(
        """
observability:
  frequency_seconds: 15
""",
        encoding="utf-8",
    )
    (run_dir / "metrics" / "metrics.om").write_text("# test\n", encoding="utf-8")

    output = write_metadata(run_dir)

    assert output.exists()
    loaded = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert loaded["run"]["manifest"] == "manifest.yaml"

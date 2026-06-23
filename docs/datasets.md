# Offline Datasets

The benchmark platform produces offline artifacts that allow a benchmark run to be reused after the live environment has been destroyed.

A complete run directory contains:

```text
manifest.yaml
config.yaml
metrics/
traffic/
kubernetes/
datasets/
logs/
```

## Raw metrics

Raw Prometheus/OpenMetrics data is stored in:

```text
metrics/metrics.om
```

The scraper adds comments around each scrape:

```text
# scrape_started_at ...
# scrape_ended_at ...
```

## Scrape metadata

Scrape-level metadata is stored in:

```text
metrics/scrapes.csv
```

Columns:

```text
scrape_index
started_at
ended_at
success
http_status
bytes_written
error
```

This file is used to detect:

- failed scrape attempts
- empty scrapes
- large gaps between scrapes
- incomplete collection windows

## Refined datasets

Refined CSV datasets are stored under:

```text
datasets/<table_family>/
```

Current table families:

```text
container_timeseries
container_metadata
pod_timeseries
pod_metadata
node_timeseries
node_metadata
controller_timeseries
controller_metadata
```

## Dataset metadata

Every generated offline dataset should include:

```text
datasets/dataset-metadata.yaml
```

This file contains:

- dataset format version
- source run manifest
- source scenario config
- raw metrics artifact
- scrape metadata artifact
- scrape frequency
- collection quality summary
- missing or incomplete collection periods
- generated table families
- schema documentation references
- provenance information such as Kubernetes artifacts and container images

## Collection quality

The `collection_quality` section summarizes whether raw metric collection was trustworthy.

Important fields:

```text
expected_scrapes
recorded_scrapes
successful_scrapes
failed_scrapes
empty_scrapes
success_ratio
missing_or_incomplete_periods
```

A dataset can exist even if collection quality is imperfect, but consumers should inspect this section before using the data for evaluation.

## Provenance

Provenance links the dataset back to:

- `manifest.yaml`
- `config.yaml`
- Kubernetes state snapshots
- container images observed in pods
- chart references when visible in logs

## Schema documentation

Detailed refined CSV schemas are documented in:

```text
docs/schemas/refined-csv.md
```

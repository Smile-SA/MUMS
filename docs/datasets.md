# Offline Datasets

The benchmark platform produces raw Prometheus/OpenMetrics data and refined CSV datasets.

## Raw metrics

Raw metrics are stored under:

```text
metrics/metrics.om
```

Scrape-level metadata is stored under:

```text
metrics/scrapes.csv
```

## Dataset metadata

Refined datasets should include:

```text
datasets/dataset-metadata.yaml
```

This file links the dataset to:

- the run manifest
- the raw metrics file
- scrape metadata
- generated table families

## Current table families

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

## Schema documentation

Every table family should document:

- key columns
- timestamp columns
- value columns
- units
- source metrics where known
- missing-value behavior

Detailed schemas are maintained under `docs/schemas/`.

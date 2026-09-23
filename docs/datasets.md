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

## Offline dataset -> HOTS

For the "offline dataset -> HOTS only" scenario (replaying a completed run's
refined dataset through the HOTS optimizer with no live cluster or Kafka),
`optimizers/hots/dataset_bridge.py` converts a run's dataset into HOTS's
`FileConnector` input shape. It lives under `optimizers/hots/` rather than
in the core `benchmark_platform` package, like everything else specific to
that optimizer:

```text
python3 optimizers/hots/dataset_bridge.py <run_dir> <output_dir> \
    [--namespace online-boutique] [--metric cpu_usage_rate] \
    [--exclude-controller-kind DaemonSet ...]
```

It reads `datasets/pod_timeseries` + `datasets/pod_metadata` (filtered to
the target namespace, excluding DaemonSet/static pods that can't
meaningfully be rescheduled by a placement optimizer) and
`datasets/node_metadata`, and writes:

```text
<output_dir>/container_usage.csv   # timestamp,pod,node,<metric> -- one row per (tick, pod)
<output_dir>/node_meta.csv         # node,<metric>                -- per-node capacity
```

`pod_timeseries` is used rather than `container_timeseries` because it is
already pod-granularity -- no container-to-pod aggregation is needed, and
`pod` matches the identity HOTS's live path uses too
(`k8s_workload_identity: pod` in `optimizers/hots/`). Short per-pod gaps in
the metric column are forward-filled, since real scrape data has gaps (a
missed scrape, a metric that only appears once cAdvisor has a second
sample) that would otherwise break HOTS's per-tick windowing.

The tool also prints the matching HOTS `data:` config section
(`tick_field: timestamp, individual_field: pod, host_field: node, metrics: [<metric>]`)
to paste into a HOTS config alongside a `connector.type: file` section
pointing `data_folder` at `<output_dir>`.

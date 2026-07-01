# observability/analysis

Pipeline that processes OpenMetrics data into structured CSVs ready for
comparative analysis of scheduling optimizers.

---

## Architecture

```
OpenMetrics stream ──┬──> container_timeseries.py ──> container_timeseries.csv
                     ├──> container_metadata.py   ──> container_metadata.csv
                     │                                        v
                     ├──> pod_metadata.py         ──> pod_metadata.csv ──┐
                     │                                                    ├──> pod_timeseries.py ──> pod_timeseries.csv
                     ├────────────────────────────────────────────────────┘
                     ├──> node_timeseries.py      ──> node_timeseries.csv
                     ├──> node_metadata.py        ──> node_metadata.csv
                     ├──> controller_timeseries.py──> controller_timeseries.csv
                     └──> controller_metadata.py  ──> controller_metadata.csv
```

The first 7 scripts read an OpenMetrics stream from **stdin** and write to **stdout**
(classic Unix pipe). `pod_timeseries.py` is an exception: it aggregates three
already-produced CSVs and takes their paths as arguments.

---

## Usage

```bash
# From a file
cat <stream.om> | ./run_all.sh <output_dir>

# Examples
cat output/run-42/metrics/metrics.om | ./run_all.sh output/run-42/datasets/

# Manually, script by script (from a file)
python3 container_timeseries.py < stream.om > container_timeseries.csv

# pod_timeseries (multi-input)
python3 pod_timeseries.py container_timeseries.csv container_metadata.csv pod_metadata.csv > pod_timeseries.csv
```

### CSV split / merge (large volume handling)

CSVs can be split into numbered files to manage large runs:

```bash
# Split into chunks of 50 000 data rows
cat container_timeseries.csv | ./csv_split.sh output/container_timeseries --lines=50000
# → output/container_timeseries/container_timeseries_1.csv
# → output/container_timeseries/container_timeseries_2.csv ...

# Reconstruct the original stream (exact inverse)
./csv_merge.sh output/container_timeseries | wc -l

# run_all.sh automatically detects split directories
# and merges them on the fly via bash process substitution
```

Each split file is a self-contained CSV (header included).
`csv_merge | csv_split` or `csv_split | csv_merge` is an identity operation.

---

## Data model

### General principle

Each category (containers, pods, nodes, controllers) is represented by two
complementary files:

| File | Content | Temporal granularity |
|------|---------|----------------------|
| `*_timeseries.csv` | Metrics that change over time | One row per (entity, timestamp) |
| `*_metadata.csv`   | Static data captured at creation | One row per entity |

Metadata is collected only once (last value seen in the scrape) because it does
not change during a benchmark run.

### Sparse rows in timeseries

Metrics come from multiple sources with independent, unsynchronized scrape cycles:

- **cAdvisor**: real-time container metrics (CPU, memory, network)
- **node_exporter**: node-level system metrics (CPU, memory, PSI pressure)
- **kube-state-metrics**: declarative Kubernetes state (allocatable, conditions, replicas)

These sources produce different timestamps for the same node or pod. Rather than
merging and losing information, the CSVs preserve all rows with some columns empty
(empty cell between commas = `NaN` in pandas/numpy/R).

**For a consolidated view**, use time-weighted linear interpolation between the
preceding and following non-null values for each column. Never discard raw data
before it is needed.

### Unique keys

| File | Unique key |
|------|-----------|
| `container_timeseries` | `(timestamp, pod, namespace, container)` |
| `container_metadata`   | `(pod, namespace, container)` |
| `pod_timeseries`       | `(timestamp, pod, namespace)` |
| `pod_metadata`         | `(pod, namespace)` |
| `node_timeseries`      | `(timestamp, node)` |
| `node_metadata`        | `(node)` |
| `controller_timeseries`| `(timestamp, controller_kind, controller_name, namespace)` |
| `controller_metadata`  | `(controller_kind, controller_name, namespace)` |

**Note on recreated pods**: when a pod dies and is recreated by its controller,
a new pod with a different name appears in `pod_timeseries` on a potentially
different node. Two `pod_metadata` rows sharing the same `controller_name` indicate
a migration or restart.

---

## Category 1 — Containers and Pods

### `container_timeseries.csv`
Key: `(timestamp, pod, namespace, container)`

| Column | Description | Source |
|--------|-------------|--------|
| `timestamp` | Prometheus scrape timestamp (ms Unix) | — |
| `pod` | Pod name | labels |
| `namespace` | Kubernetes namespace | labels |
| `container` | Container name | labels |
| `node` | Execution node | cAdvisor labels |
| `cpu_usage_rate` | CPU consumption (cores/s), rate of cumulative counter | `container_cpu_usage_seconds_total` |
| `memory_working_set_bytes` | Active memory (Kubernetes reference for OOM/limits) | `container_memory_working_set_bytes` |
| `memory_rss_bytes` | Process RSS memory (heap+stack, excluding cache) | `container_memory_rss` |
| `cpu_throttled_ratio` | Fraction of CFS periods where the container was throttled | `container_cpu_cfs_throttled_seconds_total` / `container_cpu_cfs_periods_total` |
| `network_receive_bytes_rate` | Inbound network throughput (bytes/s) | `container_network_receive_bytes_total` |
| `network_transmit_bytes_rate` | Outbound network throughput (bytes/s) | `container_network_transmit_bytes_total` |
| `oom_events_total` | Cumulative OOM kill count | `container_oom_events_total` |
| `restarts_total` | Cumulative restart count | `kube_pod_container_status_restarts_total` |

**Note on rates**: `cpu_usage_rate` and network throughput are discrete derivatives
`(v2 - v1) / (t2 - t1)`. The first point of each series has no computable rate →
empty cell.

---

### `container_metadata.csv`
Key: `(pod, namespace, container)`

| Column | Description | Source |
|--------|-------------|--------|
| `pod` | Pod name | — |
| `namespace` | Kubernetes namespace | — |
| `container` | Container name | — |
| `image` | Container Docker image | `kube_pod_container_info` |
| `cpu_request` | Guaranteed CPU (cores) | `kube_pod_container_resource_requests{resource="cpu"}` |
| `memory_request` | Guaranteed memory (bytes) | `kube_pod_container_resource_requests{resource="memory"}` |
| `cpu_limit` | CPU ceiling — throttling if exceeded (cores) | `kube_pod_container_resource_limits{resource="cpu"}` |
| `memory_limit` | Memory ceiling — OOM kill if exceeded (bytes) | `kube_pod_container_resource_limits{resource="memory"}` |

**Requests vs Limits**:
- `request` = resource guaranteed by the scheduler, used for placement decisions
- `cpu_limit` = soft ceiling (CFS throttling if exceeded, no kill)
- `memory_limit` = hard ceiling (immediate OOM kill if exceeded)
- A container without a limit can consume all available resources (BestEffort)

---

### `pod_timeseries.csv`
Key: `(timestamp, pod, namespace)`

Aggregation of `container_timeseries` by pod. Generated by `pod_timeseries.py`.

| Column | Aggregation |
|--------|-------------|
| `cpu_usage_rate` | Sum of containers |
| `memory_working_set_bytes` | Sum of containers |
| `memory_rss_bytes` | Sum of containers |
| `cpu_throttled_ratio` | Weighted average by `cpu_request` of each container |
| `network_receive_bytes_rate` | Sum of containers |
| `network_transmit_bytes_rate` | Sum of containers |
| `oom_events_total` | Sum of containers |
| `restarts_total` | Sum of containers |

---

### `pod_metadata.csv`
Key: `(pod, namespace)`

| Column | Description | Source |
|--------|-------------|--------|
| `pod` | Pod name | — |
| `namespace` | Kubernetes namespace | — |
| `node` | Execution node | `kube_pod_info` |
| `controller_kind` | Parent controller type (`ReplicaSet`, `StatefulSet`, `DaemonSet`, `Job`, empty for static pods) | `kube_pod_owner` |
| `controller_name` | Parent controller name | `kube_pod_owner` |
| `qos_class` | QoS class (`Guaranteed`, `Burstable`, `BestEffort`) | `kube_pod_status_qos_class` |
| `created_time` | Creation timestamp in etcd (Unix s) | `kube_pod_created` |
| `scheduled_time` | Timestamp of scheduler placement decision (Unix s) | `kube_pod_status_scheduled_time` |
| `running_time` | Timestamp when containers started (Unix s) | `kube_pod_status_initialized_time` |
| `ready_time` | Timestamp when pod is ready to receive traffic (Unix s) | `kube_pod_status_ready_time` |
| `succeeded_time` | First scrape where phase=Succeeded (nullable, ±15 s) | `kube_pod_status_phase` |
| `failed_time` | First scrape where phase=Failed (nullable, ±15 s) | `kube_pod_status_phase` |

**Pod phases** are strictly unidirectional: `Pending → Running → Succeeded/Failed`.
A restarting container stays in `Running` — restarts are captured in
`container_timeseries.restarts_total`.

**Time in Pending** = `scheduled_time - created_time`
**Startup time** = `ready_time - scheduled_time` (includes image pull)

---

## Category 2 — Nodes

### `node_timeseries.csv`
Key: `(timestamp, node)`

| Column | Description | Source |
|--------|-------------|--------|
| `timestamp` | Scrape timestamp (ms Unix) | — |
| `node` | Node name | labels |
| `cpu_usage_ratio` | CPU utilization ratio (0–1) = `1 - rate(idle) / sum(all modes)` | `node_cpu_seconds_total` |
| `memory_used_bytes` | Memory used = MemTotal - MemAvailable | `node_memory_MemTotal/MemAvailable_bytes` |
| `memory_allocatable_bytes` | Memory allocatable to pods | `kube_node_status_allocatable{resource="memory"}` |
| `cpu_pressure_waiting_seconds_total` | Cumulative time tasks waited for CPU (PSI) | `node_pressure_cpu_waiting_seconds_total` |
| `memory_pressure_waiting_seconds_total` | Cumulative time tasks waited for memory (PSI) | `node_pressure_memory_waiting_seconds_total` |
| `memory_pressure_stalled_seconds_total` | Cumulative time tasks stalled on memory (PSI) | `node_pressure_memory_stalled_seconds_total` |
| `condition_ready` | 1 if node is Ready, 0 otherwise | `kube_node_status_condition{condition="Ready"}` |
| `unschedulable` | 1 if node is cordoned (drain in progress) | `kube_node_spec_unschedulable` |
| `up` | 1 if node responds to scrape, 0 if unreachable | `up{job="kubernetes-nodes"}` |

**Failure detection**: `up=0` signals network unreachability at the next scrape
(~15 s). `condition_ready=0` or `Unknown` arrives after ~40 s (node controller delay).
Both signals are complementary.

---

### `node_metadata.csv`
Key: `(node)`

| Column | Description | Source |
|--------|-------------|--------|
| `node` | Node name | — |
| `cpu_allocatable` | CPU allocatable to pods (cores) | `kube_node_status_allocatable{resource="cpu"}` |
| `memory_allocatable` | Memory allocatable to pods (bytes) | `kube_node_status_allocatable{resource="memory"}` |
| `architecture` | CPU architecture (e.g. `amd64`) | `kube_node_info` |
| `os` | OS (e.g. `linux`) | `kube_node_info` |
| `kernel_version` | Kernel version | `kube_node_info` |
| `taints` | Node taints (JSON) | `kube_node_spec_taint` |
| `created_time` | Node registration timestamp (Unix s) | `kube_node_created` |

**Allocatable vs Capacity**: `allocatable` is what is actually available to pods
(capacity minus system-reserved resources). This is the correct reference for
evaluating node pressure.

---

## Category 3 — Controllers

### `controller_timeseries.csv`
Key: `(timestamp, controller_kind, controller_name, namespace)`

| Column | Description | Source |
|--------|-------------|--------|
| `timestamp` | Scrape timestamp (ms Unix) | — |
| `controller_kind` | `ReplicaSet`, `StatefulSet`, `DaemonSet`, `Job` | — |
| `controller_name` | Controller name | labels |
| `namespace` | Kubernetes namespace | labels |
| `replicas_desired` | Desired replica count | `kube_*_spec_replicas` / `kube_daemonset_status_desired_*` |
| `replicas_ready` | Replicas ready to receive traffic | `kube_*_status_ready_replicas` / `kube_daemonset_status_number_ready` |

**Application availability**: `replicas_ready / replicas_desired` at each instant
is the primary availability KPI. A value < 1 indicates service degradation —
caused by rescheduling, a crash, or a migration.

---

### `controller_metadata.csv`
Key: `(controller_kind, controller_name, namespace)`

| Column | Description | Source |
|--------|-------------|--------|
| `controller_kind` | Controller type | — |
| `controller_name` | Controller name | — |
| `namespace` | Kubernetes namespace | — |
| `parent_kind` | Parent type (e.g. `Deployment` for a `ReplicaSet`) | `kube_replicaset_owner` |
| `parent_name` | Parent name | `kube_replicaset_owner` |
| `replicas_desired` | Desired replica count (initial value) | `kube_*_spec_replicas` |

---

## Scripts

| Script | Role | Input | Output |
|--------|------|-------|--------|
| `run_all.sh` | Orchestrates generation of all 8 CSVs | stdin (OpenMetrics) + `output_dir` | 8 CSV files |
| `container_timeseries.py` | Container time series | stdin (OpenMetrics) | stdout (CSV) |
| `container_metadata.py` | Container metadata | stdin (OpenMetrics) | stdout (CSV) |
| `pod_metadata.py` | Pod metadata | stdin (OpenMetrics) | stdout (CSV) |
| `node_timeseries.py` | Node time series | stdin (OpenMetrics) | stdout (CSV) |
| `node_metadata.py` | Node metadata | stdin (OpenMetrics) | stdout (CSV) |
| `controller_timeseries.py` | Controller time series | stdin (OpenMetrics) | stdout (CSV) |
| `controller_metadata.py` | Controller metadata | stdin (OpenMetrics) | stdout (CSV) |
| `pod_timeseries.py` | Container → pod aggregation | 3 CSV files (args) | stdout (CSV) |
| `csv_split.sh` | Splits a CSV into numbered files | stdin (CSV) + directory | `directory/basename_N.csv` |
| `csv_merge.sh` | Reconstructs a CSV stream from a directory | directory | stdout (CSV) |

---

## See also

- [`docs/known-limitations.md`](../../docs/known-limitations.md) — open questions and future work
- [`observability/prometheus/`](../prometheus/) — scraping scripts and port-forward management
- [`utils/scraper/scraper.py`](../../utils/scraper/scraper.py) — Prometheus → OpenMetrics (.om) scraper

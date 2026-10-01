# post-processing.essential-tables

Post-processing module: turns the raw OpenMetrics scrapes of a run into eight
tables holding the **essential data about the cluster's objects and their use**
(containers, pods, nodes, controllers). It is the intermediate refinement step:
a large mass of raw data, mostly irrelevant, becomes a smaller, organized set of
tables that other post-processing modules build on (instances, evaluation...).

## Action

- `run <data_dir>`: reads `<data_dir>/openmetrics/*.om` (in order) and writes
  `<data_dir>/essential-tables/`. Does nothing if there is no scrape.

## Data consumed

`openmetrics`: one OpenMetrics file per scrape (`<data_dir>/openmetrics/<index>.om`).

## Data produced: `essential-tables`

`<data_dir>/essential-tables/<table>/<table>_<n>.csv`: one directory per table,
each split into files of 100,000 rows (each with its header). All times are
Unix seconds (with decimals), all durations seconds.


## Data model

### General principle

Each category (containers, pods, nodes, controllers) is represented by two
complementary files:

| File | Content | Temporal granularity |
|------|---------|----------------------|
| `*_timeseries` | Metrics that change over time | One row per (entity, timestamp) |
| `*_metadata`   | Descriptive data, no time | One row per entity |

Every object seen during the run is listed (all namespaces, deleted pods
included). Metadata tables have no time column: they hold the **last** value
observed during the run (some values are empty at first, such as a pod's node
before it is scheduled).

### Sparse rows in timeseries

Metrics come from multiple sources with independent, unsynchronized scrape cycles:

- **cAdvisor**: real-time container metrics (CPU, memory, network)
- **node_exporter**: node-level system metrics (CPU, memory, PSI pressure)
- **kube-state-metrics**: declarative Kubernetes state (allocatable, conditions, replicas)

These sources produce different timestamps for the same node or pod. Rather than
merging and losing information, the CSVs preserve all rows with some columns empty
(empty cell between commas = `NaN` in pandas/numpy/R). A value is never invented:
**a non-empty cell is a measured value** (or, for rates and ratios, computed from
two measured values, see below); **an empty cell means unknown**, never 0.

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
different node. Two `pod_metadata` rows sharing the same `controller_name` may
indicate a migration.

---

## Category 1 — Containers and Pods

### `container_timeseries`
Key: `(timestamp, pod, namespace, container)`

| Column | Description | Source |
|--------|-------------|--------|
| `timestamp` | Sample timestamp, set by Prometheus (Unix s) | — |
| `pod` | Pod name | labels |
| `namespace` | Kubernetes namespace | labels |
| `container` | Container name | labels |
| `node` | Execution node | cAdvisor labels |
| `cpu_usage_rate` | CPU consumption (cores), rate of a cumulative counter | `container_cpu_usage_seconds_total` |
| `memory_working_set_bytes` | Active memory (Kubernetes reference for OOM/limits) | `container_memory_working_set_bytes` |
| `memory_rss_bytes` | Process RSS memory (heap+stack, excluding cache) | `container_memory_rss` |
| `cpu_throttled_ratio` | Fraction of CFS periods where the container was throttled | `container_cpu_cfs_throttled_seconds_total` / `container_cpu_cfs_periods_total` |
| `network_receive_bytes_rate` | Inbound network throughput (bytes/s) | `container_network_receive_bytes_total` |
| `network_transmit_bytes_rate` | Outbound network throughput (bytes/s) | `container_network_transmit_bytes_total` |
| `oom_events_total` | Cumulative OOM kill count | `container_oom_events_total` |
| `restarts_total` | Cumulative restart count | `kube_pod_container_status_restarts_total` |

**Note on rates**: CPU and network are cumulative counters (e.g. CPU seconds used
since the container started). Their usage is the slope between two samples of the
**same** metric, `(v2 - v1) / (t2 - t1)`, whatever rows of other sources lie in
between: a rate is an average over that window, the only non-empty values that are
not measured directly. After a container creation or restart, the counter starts
from 0 at the container start time (`container_start_time_seconds`): the first
sample then gives the usage since that start, and a restart never gives a negative
value. `cpu_throttled_ratio` follows the same rules.

---

### `container_metadata`
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

### `pod_timeseries`
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

### `pod_metadata`
Key: `(pod, namespace)`

| Column | Description | Source |
|--------|-------------|--------|
| `pod` | Pod name | — |
| `namespace` | Kubernetes namespace | — |
| `node` | Execution node | `kube_pod_info` |
| `controller_kind` | Owner controller type, whatever it is (`ReplicaSet`, `StatefulSet`, `DaemonSet`, `Job`, a custom kind...; empty for pods without owner) | `kube_pod_owner` |
| `controller_name` | Parent controller name | `kube_pod_owner` |
| `qos_class` | QoS class (`Guaranteed`, `Burstable`, `BestEffort`) | `kube_pod_status_qos_class` |
| `created_time` | Creation timestamp in etcd (Unix s) | `kube_pod_created` |
| `scheduled_time` | Timestamp of scheduler placement decision (Unix s) | `kube_pod_status_scheduled_time` |
| `running_time` | Timestamp when containers started (Unix s) | `kube_pod_status_initialized_time` |
| `ready_time` | Timestamp when pod is ready to receive traffic (Unix s) | `kube_pod_status_ready_time` |
| `succeeded_time` | First sample where phase=Succeeded (nullable; precision: the scrape period) | `kube_pod_status_phase` |
| `failed_time` | First sample where phase=Failed (nullable; precision: the scrape period) | `kube_pod_status_phase` |

**Pod phases** are strictly unidirectional: `Pending → Running → Succeeded/Failed`.
A restarting container stays in `Running` — restarts are captured in
`container_timeseries.restarts_total`.

**Time in Pending** = `scheduled_time - created_time`
**Startup time** = `ready_time - scheduled_time` (includes image pull)

---

## Category 2 — Nodes

### `node_timeseries`
Key: `(timestamp, node)`

| Column | Description | Source |
|--------|-------------|--------|
| `timestamp` | Sample timestamp, set by Prometheus (Unix s) | — |
| `node` | Node name | labels |
| `cpu_usage_ratio` | CPU utilization ratio (0–1) = `1 - rate(idle) / sum(all modes)`, over all the node's cores, between two samples of the CPU counters | `node_cpu_seconds_total` |
| `memory_used_bytes` | Memory used = MemTotal - MemAvailable | `node_memory_MemTotal/MemAvailable_bytes` |
| `memory_allocatable_bytes` | Memory allocatable to pods | `kube_node_status_allocatable{resource="memory"}` |
| `cpu_pressure_waiting_seconds_total` | Cumulative time tasks waited for CPU (PSI) | `node_pressure_cpu_waiting_seconds_total` |
| `memory_pressure_waiting_seconds_total` | Cumulative time tasks waited for memory (PSI) | `node_pressure_memory_waiting_seconds_total` |
| `memory_pressure_stalled_seconds_total` | Cumulative time tasks stalled on memory (PSI) | `node_pressure_memory_stalled_seconds_total` |
| `condition_ready` | 1 if node is Ready, 0 otherwise | `kube_node_status_condition{condition="Ready"}` |
| `unschedulable` | 1 if node is cordoned (drain in progress) | `kube_node_spec_unschedulable` |
| `up` | 1 if node responds to scrape, 0 if unreachable | `up{job="kubernetes-nodes"}` |

**Node-exporter metrics** (`cpu_usage_ratio`, `memory_used_bytes`, the pressure
columns) are those the node exporter sees: the machine running the node. When a
node shares its machine's kernel with other nodes (e.g. nodes run as containers
on one host), they describe that machine, not the node. A node's own usage is the
sum of its pods' usage (`pod_timeseries`), against its allocatable (`node_metadata`).

**Failure detection**: `up=0` signals network unreachability at the next scrape.
`condition_ready=0` or `Unknown` arrives after ~40 s (node controller delay).
Both signals are complementary.

---

### `node_metadata`
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

### `controller_timeseries`
Key: `(timestamp, controller_kind, controller_name, namespace)`

| Column | Description | Source |
|--------|-------------|--------|
| `timestamp` | Sample timestamp, set by Prometheus (Unix s) | — |
| `controller_kind` | `Deployment`, `ReplicaSet`, `StatefulSet`, `DaemonSet`, `Job`: the kinds whose replica counts kube-state-metrics exposes | — |
| `controller_name` | Controller name | labels |
| `namespace` | Kubernetes namespace | labels |
| `replicas_desired` | Desired replica count (Jobs: active pods) | `kube_*_spec_replicas` / `kube_daemonset_status_desired_*` / `kube_job_status_active` |
| `replicas_ready` | Replicas ready to receive traffic (Jobs: succeeded pods) | `kube_*_status_ready_replicas` / `kube_daemonset_status_number_ready` / `kube_job_status_succeeded` |

**Application availability**: `replicas_ready / replicas_desired` at each instant
is the primary availability KPI. A value < 1 indicates service degradation —
caused by rescheduling, a crash, or a migration.

---

### `controller_metadata`
Key: `(controller_kind, controller_name, namespace)`

| Column | Description | Source |
|--------|-------------|--------|
| `controller_kind` | Controller type, whatever it is (custom and future kinds included) | `kube_pod_owner`, `kube_replicaset_owner`, `kube_job_owner` |
| `controller_name` | Controller name | — |
| `namespace` | Kubernetes namespace | — |
| `parent_kind` | Parent type (e.g. `Deployment` for a `ReplicaSet`, `CronJob` for a `Job`) | `kube_replicaset_owner`, `kube_job_owner` |
| `parent_name` | Parent name | `kube_replicaset_owner`, `kube_job_owner` |
| `replicas_desired` | Desired replica count, for the kinds kube-state-metrics describes | `kube_*_spec_replicas`, ... |

Every controller is listed, found through the generic owner metrics of
kube-state-metrics rather than a list of known kinds; parents are listed too.

---

## Scripts

| Script | Role | Input | Output |
|--------|------|-------|--------|
| `run.sh` | Module action: reads `<data_dir>/openmetrics/`, writes `<data_dir>/essential-tables/` | `<data_dir>` | 8 tables |
| `run_all.sh` | Orchestrates generation of all 8 CSVs | stdin (OpenMetrics) + output directory | 8 tables |
| `container_timeseries.py` | Container time series | stdin (OpenMetrics) | stdout (CSV) |
| `container_metadata.py` | Container metadata | stdin (OpenMetrics) | stdout (CSV) |
| `pod_metadata.py` | Pod metadata | stdin (OpenMetrics) | stdout (CSV) |
| `node_timeseries.py` | Node time series | stdin (OpenMetrics) | stdout (CSV) |
| `node_metadata.py` | Node metadata | stdin (OpenMetrics) | stdout (CSV) |
| `controller_timeseries.py` | Controller time series | stdin (OpenMetrics) | stdout (CSV) |
| `controller_metadata.py` | Controller metadata | stdin (OpenMetrics) | stdout (CSV) |
| `pod_timeseries.py` | Container → pod aggregation | 3 CSV files (args) | stdout (CSV) |
| `csv_split.py` | Splits a CSV into numbered files | stdin (CSV) + directory | `directory/basename_N.csv` |

---

## Dependencies

python3.

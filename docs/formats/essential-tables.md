# Format `essential-tables`

Eight tables holding the **essential data about the cluster's objects and their
use**: containers, pods, nodes, controllers. A smaller, organized set of tables,
refined from the raw metrics, that evaluations build on.

## Files

`<data_dir>/essential-tables/<table>/<table>_<n>.csv`: one directory per table,
each split into files of at most 100,000 rows (`<table>_1.csv`, `<table>_2.csv`...),
each with its header. All times are Unix seconds (with decimals), all durations
seconds.

## General principle

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

## Sparse rows in timeseries

The measures of an entity come from several sources, collected at different
instants. Rather than merging them and losing information, the tables keep every
row, with some columns empty (empty cell between commas = `NaN` in pandas/numpy/R). A value is never invented:
**a non-empty cell is a measured value** (or, for rates and ratios, computed from
two measured values, see below); **an empty cell means unknown**, never 0.

**For a consolidated view**, use time-weighted linear interpolation between the
preceding and following non-null values for each column. Never discard raw data
before it is needed.

## Unique keys

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


## Category 1 — Containers and Pods

### `container_timeseries`
Key: `(timestamp, pod, namespace, container)`

| Column | Description |
|--------|-------------|
| `timestamp` | Sample timestamp, (Unix s) |
| `pod` | Pod name |
| `namespace` | Kubernetes namespace |
| `container` | Container name |
| `node` | Execution node |
| `cpu_usage_rate` | CPU consumption (cores), rate of a cumulative counter |
| `memory_working_set_bytes` | Active memory (Kubernetes reference for OOM/limits) |
| `memory_rss_bytes` | Process RSS memory (heap+stack, excluding cache) |
| `cpu_throttled_ratio` | Fraction of CFS periods where the container was throttled |
| `network_receive_bytes_rate` | Inbound network throughput (bytes/s); measured per pod, hence empty per container (see `pod_timeseries`) |
| `network_transmit_bytes_rate` | Outbound network throughput (bytes/s); measured per pod, hence empty per container (see `pod_timeseries`) |
| `oom_events_total` | Cumulative OOM kill count |
| `restarts_total` | Cumulative restart count |

**Note on rates**: CPU and network are cumulative counters (e.g. CPU seconds used
since the container started). Their usage is the slope between two samples of the
**same** metric, `(v2 - v1) / (t2 - t1)`, whatever rows of other sources lie in
between: a rate is an average over that window, the only non-empty values that are
not measured directly. After a container creation or restart, the counter starts
from 0 when the container starts: the first
sample then gives the usage since that start, and a restart never gives a negative
value. `cpu_throttled_ratio` follows the same rules.


### `container_metadata`
Key: `(pod, namespace, container)`

| Column | Description |
|--------|-------------|
| `pod` | Pod name |
| `namespace` | Kubernetes namespace |
| `container` | Container name |
| `image` | Container Docker image |
| `cpu_request` | Guaranteed CPU (cores) |
| `memory_request` | Guaranteed memory (bytes) |
| `cpu_limit` | CPU ceiling — throttling if exceeded (cores) |
| `memory_limit` | Memory ceiling — OOM kill if exceeded (bytes) |

**Requests vs Limits**:
- `request` = resource guaranteed by the scheduler, used for placement decisions
- `cpu_limit` = soft ceiling (CFS throttling if exceeded, no kill)
- `memory_limit` = hard ceiling (immediate OOM kill if exceeded)
- A container without a limit can consume all available resources (BestEffort)


### `pod_timeseries`
Key: `(timestamp, pod, namespace)`

One measure of the whole pod per sample (all its containers, and the pod's own
sandbox). Same columns and rules as `container_timeseries`, without `container`:

| Column | Description |
|--------|-------------|
| `timestamp` | Sample timestamp (Unix s) |
| `pod` | Pod name |
| `namespace` | Kubernetes namespace |
| `node` | Execution node |
| `cpu_usage_rate` | CPU consumption of the pod (cores) |
| `memory_working_set_bytes` | Active memory of the pod |
| `memory_rss_bytes` | RSS memory of the pod |
| `cpu_throttled_ratio` | Fraction of CFS periods where the pod was throttled |
| `network_receive_bytes_rate` | Inbound network throughput of the pod (bytes/s) |
| `network_transmit_bytes_rate` | Outbound network throughput of the pod (bytes/s) |
| `oom_events_total` | Cumulative OOM kill count |
| `restarts_total` | Cumulative restart count, over the pod's containers |

### `pod_metadata`
Key: `(pod, namespace)`

| Column | Description |
|--------|-------------|
| `pod` | Pod name |
| `namespace` | Kubernetes namespace |
| `node` | Execution node |
| `controller_kind` | Owner controller type, whatever it is (`ReplicaSet`, `StatefulSet`, `DaemonSet`, `Job`, a custom kind...; empty for pods without owner) |
| `controller_name` | Parent controller name |
| `qos_class` | QoS class (`Guaranteed`, `Burstable`, `BestEffort`) |
| `created_time` | Creation timestamp in etcd (Unix s) |
| `scheduled_time` | Timestamp of scheduler placement decision (Unix s) |
| `running_time` | Timestamp when containers started (Unix s) |
| `ready_time` | Timestamp when pod is ready to receive traffic (Unix s) |
| `succeeded_time` | First sample where phase=Succeeded (empty if never; precision: the collection period) |
| `failed_time` | First sample where phase=Failed (empty if never; precision: the collection period) |

**Pod phases** are strictly unidirectional: `Pending → Running → Succeeded/Failed`.
A restarting container stays in `Running` — restarts are captured in
`container_timeseries.restarts_total`.

**Time in Pending** = `scheduled_time - created_time`
**Startup time** = `ready_time - scheduled_time` (includes image pull)


## Category 2 — Nodes

### `node_timeseries`
Key: `(timestamp, node)`

| Column | Description |
|--------|-------------|
| `timestamp` | Sample timestamp, (Unix s) |
| `node` | Node name |
| `cpu_usage_ratio` | CPU utilization ratio (0–1) = `1 - rate(idle) / sum(all modes)`, over all the node's cores, between two samples of the CPU counters |
| `memory_used_bytes` | Memory used = MemTotal - MemAvailable |
| `memory_total_bytes` | Total memory of the machine |
| `memory_allocatable_bytes` | Memory allocatable to pods |
| `cpu_pressure_waiting_seconds_total` | Cumulative time tasks waited for CPU (PSI) |
| `memory_pressure_waiting_seconds_total` | Cumulative time tasks waited for memory (PSI) |
| `memory_pressure_stalled_seconds_total` | Cumulative time tasks stalled on memory (PSI) |
| `condition_ready` | 1 if node is Ready, 0 otherwise |
| `unschedulable` | 1 if node is cordoned (drain in progress) |
| `up` | 1 if node responds to scrape, 0 if unreachable |

**Machine-level columns** (`cpu_usage_ratio`, `memory_used_bytes`, `memory_total_bytes`, the pressure
columns) describe the machine running the node. When a
node shares its machine's kernel with other nodes (e.g. nodes run as containers
on one host), they describe that machine, not the node. A node's own usage can be computed
from its pods' usage (`pod_timeseries`), against its allocatable (`node_metadata`).

**Failure detection**: `up=0` signals that the node did not answer a collection.
`condition_ready=0` or `Unknown` arrives after ~40 s (node controller delay).
Both signals are complementary.


### `node_metadata`
Key: `(node)`

| Column | Description |
|--------|-------------|
| `node` | Node name |
| `cpu_allocatable` | CPU allocatable to pods (cores) |
| `memory_allocatable` | Memory allocatable to pods (bytes) |
| `architecture` | CPU architecture (e.g. `amd64`) |
| `os` | OS (e.g. `linux`) |
| `kernel_version` | Kernel version |
| `taints` | Node taints (JSON) |
| `created_time` | Node registration timestamp (Unix s) |

**Allocatable vs Capacity**: `allocatable` is what is actually available to pods
(capacity minus system-reserved resources). This is the correct reference for
evaluating node pressure.


## Category 3 — Controllers

### `controller_timeseries`
Key: `(timestamp, controller_kind, controller_name, namespace)`

| Column | Description |
|--------|-------------|
| `timestamp` | Sample timestamp, (Unix s) |
| `controller_kind` | `Deployment`, `ReplicaSet`, `StatefulSet`, `DaemonSet`, `Job`: the kinds with replica counts |
| `controller_name` | Controller name |
| `namespace` | Kubernetes namespace |
| `replicas_desired` | Desired replica count (Jobs: active pods) |
| `replicas_ready` | Replicas ready to receive traffic (Jobs: succeeded pods) |

**Application availability**: `replicas_ready / replicas_desired` at each instant
is the primary availability KPI. A value < 1 indicates service degradation —
caused by rescheduling, a crash, or a migration.


### `controller_metadata`
Key: `(controller_kind, controller_name, namespace)`

| Column | Description |
|--------|-------------|
| `controller_kind` | Controller type, whatever it is (custom and future kinds included) |
| `controller_name` | Controller name |
| `namespace` | Kubernetes namespace |
| `parent_kind` | Parent type (e.g. `Deployment` for a `ReplicaSet`, `CronJob` for a `Job`) |
| `parent_name` | Parent name |
| `replicas_desired` | Desired replica count, for the kinds that have one |

Every controller is listed, whatever its kind; parents are listed too.


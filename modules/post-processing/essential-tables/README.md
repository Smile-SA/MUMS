# essential-tables

Post-processing module: turns the raw OpenMetrics scrapes of a run into eight
tables holding the **essential data about the cluster's objects and their use**
(containers, pods, nodes, controllers). It is the intermediate refinement step:
a large mass of raw data, mostly irrelevant, becomes a smaller, organized set of
tables that other post-processing modules build on (instances, evaluation...).

## Actions

- `run <data_dir>`: reads `<data_dir>/openmetrics/*.om` (in order) and writes
  `<data_dir>/essential-tables/`. Does nothing if there is no scrape.

## Arguments

None.

## Data consumed

`openmetrics`: one OpenMetrics file per scrape (`<data_dir>/openmetrics/<index>.om`).

## Data produced

`essential-tables`: the eight tables of the platform's format `essential-tables`,
which describes their columns. Below, how this module computes them.

## How the tables are computed

The tables are read from three sources found in the scrapes, collected at
different instants (hence the sparse rows of the timeseries):

- **cAdvisor**: real-time container and pod metrics (CPU, memory, network);
- **node-exporter**: metrics of the machine running each node (CPU, memory, PSI
  pressure);
- **kube-state-metrics**: the declarative Kubernetes state (allocatable,
  conditions, replicas, owners).

Rates (CPU, network, throttling) are the slope between two samples of the same
counter; after a container's creation or restart, its counter starts from 0 at
`container_start_time_seconds`. `pod_timeseries` reads cAdvisor's pod-level series
(the pod's cgroup), not the sum of its containers.


### `container_timeseries`

| Column | Source |
|--------|--------|
| `pod` | labels |
| `namespace` | labels |
| `container` | labels |
| `node` | cAdvisor labels |
| `cpu_usage_rate` | `container_cpu_usage_seconds_total` |
| `memory_working_set_bytes` | `container_memory_working_set_bytes` |
| `memory_rss_bytes` | `container_memory_rss` |
| `cpu_throttled_ratio` | `container_cpu_cfs_throttled_seconds_total` / `container_cpu_cfs_periods_total` |
| `network_receive_bytes_rate` | `container_network_receive_bytes_total` |
| `network_transmit_bytes_rate` | `container_network_transmit_bytes_total` |
| `oom_events_total` | `container_oom_events_total` |
| `restarts_total` | `kube_pod_container_status_restarts_total` |

### `container_metadata`

| Column | Source |
|--------|--------|
| `image` | `kube_pod_container_info` |
| `cpu_request` | `kube_pod_container_resource_requests{resource="cpu"}` |
| `memory_request` | `kube_pod_container_resource_requests{resource="memory"}` |
| `cpu_limit` | `kube_pod_container_resource_limits{resource="cpu"}` |
| `memory_limit` | `kube_pod_container_resource_limits{resource="memory"}` |

### `pod_timeseries`

| Column | Source |
|--------|--------|
| `cpu_usage_rate`, `memory_working_set_bytes`, `memory_rss_bytes`, `cpu_throttled_ratio`, `oom_events_total` | pod-level series of the same metrics as `container_timeseries` |
| `network_receive_bytes_rate`, `network_transmit_bytes_rate` | pod-level series (a pod has one network namespace, shared by its containers), summed over its interfaces |
| `restarts_total` | sum over the pod's containers (`kube_pod_container_status_restarts_total`) |

### `pod_metadata`

| Column | Source |
|--------|--------|
| `node` | `kube_pod_info` |
| `controller_kind` | `kube_pod_owner` |
| `controller_name` | `kube_pod_owner` |
| `qos_class` | `kube_pod_status_qos_class` |
| `created_time` | `kube_pod_created` |
| `scheduled_time` | `kube_pod_status_scheduled_time` |
| `running_time` | `kube_pod_status_initialized_time` |
| `ready_time` | `kube_pod_status_ready_time` |
| `succeeded_time` | `kube_pod_status_phase` |
| `failed_time` | `kube_pod_status_phase` |

### `node_timeseries`

| Column | Source |
|--------|--------|
| `node` | labels |
| `cpu_usage_ratio` | `node_cpu_seconds_total` |
| `memory_used_bytes` | `node_memory_MemTotal/MemAvailable_bytes` |
| `memory_total_bytes` | `node_memory_MemTotal_bytes` |
| `memory_allocatable_bytes` | `kube_node_status_allocatable{resource="memory"}` |
| `cpu_pressure_waiting_seconds_total` | `node_pressure_cpu_waiting_seconds_total` |
| `memory_pressure_waiting_seconds_total` | `node_pressure_memory_waiting_seconds_total` |
| `memory_pressure_stalled_seconds_total` | `node_pressure_memory_stalled_seconds_total` |
| `condition_ready` | `kube_node_status_condition{condition="Ready"}` |
| `unschedulable` | `kube_node_spec_unschedulable` |
| `up` | `up{job="kubernetes-nodes"}` |

### `node_metadata`

| Column | Source |
|--------|--------|
| `cpu_allocatable` | `kube_node_status_allocatable{resource="cpu"}` |
| `memory_allocatable` | `kube_node_status_allocatable{resource="memory"}` |
| `architecture` | `kube_node_info` |
| `os` | `kube_node_info` |
| `kernel_version` | `kube_node_info` |
| `taints` | `kube_node_spec_taint` |
| `created_time` | `kube_node_created` |

### `controller_timeseries`

| Column | Source |
|--------|--------|
| `controller_name` | labels |
| `namespace` | labels |
| `replicas_desired` | `kube_*_spec_replicas` / `kube_daemonset_status_desired_*` / `kube_job_status_active` |
| `replicas_ready` | `kube_*_status_ready_replicas` / `kube_daemonset_status_number_ready` / `kube_job_status_succeeded` |

### `controller_metadata`

| Column | Source |
|--------|--------|
| `controller_kind` | `kube_pod_owner`, `kube_replicaset_owner`, `kube_job_owner` |
| `parent_kind` | `kube_replicaset_owner`, `kube_job_owner` |
| `parent_name` | `kube_replicaset_owner`, `kube_job_owner` |
| `replicas_desired` | `kube_*_spec_replicas`, ... |

## Files

| File | Role | Input | Output |
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
| `pod_timeseries.py` | Pod-level series | stdin (OpenMetrics) + `pod_metadata.csv` (arg) | stdout (CSV) |
| `csv_split.py` | Splits a CSV into numbered files | stdin (CSV) + directory | `directory/basename_N.csv` |
| `module.yaml` | Module descriptor | | |

---

## Dependencies

python3.

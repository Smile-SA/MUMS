# Refined CSV Schema Reference

This document describes the refined CSV table families generated from `metrics/metrics.om`.

The exact column set must stay synchronized with scripts under:

```text
observability/analysis/
```

## container_timeseries

Granularity:

```text
timestamp + pod + namespace + container
```

Columns:

| Column | Type | Unit | Description |
|---|---:|---:|---|
| timestamp | integer | ms | Prometheus sample timestamp. |
| pod | string | - | Pod name. |
| namespace | string | - | Kubernetes namespace. |
| container | string | - | Container name. |
| node | string | - | Node where the pod is scheduled when available. |
| cpu_usage_rate | float | CPU seconds/s | Rate from `container_cpu_usage_seconds_total`. |
| memory_working_set_bytes | float | bytes | Container working set memory. |
| memory_rss_bytes | float | bytes | Container RSS memory. |
| cpu_throttled_ratio | float | ratio | Derived CPU throttling ratio. |
| network_receive_bytes_rate | float | bytes/s | Receive network rate. |
| network_transmit_bytes_rate | float | bytes/s | Transmit network rate. |
| oom_events_total | float | count | OOM events. |
| restarts_total | float | count | Container restarts. |

## container_metadata

Granularity:

```text
pod + namespace + container
```

Columns:

| Column | Type | Unit | Description |
|---|---:|---:|---|
| pod | string | - | Pod name. |
| namespace | string | - | Kubernetes namespace. |
| container | string | - | Container name. |
| image | string | - | Container image. |
| cpu_request | float | cores | CPU request. |
| memory_request | float | bytes | Memory request. |
| cpu_limit | float | cores | CPU limit. |
| memory_limit | float | bytes | Memory limit. |

## pod_timeseries

Granularity:

```text
timestamp + pod + namespace
```

Columns:

| Column | Type | Unit | Description |
|---|---:|---:|---|
| timestamp | integer | ms | Prometheus sample timestamp. |
| pod | string | - | Pod name. |
| namespace | string | - | Kubernetes namespace. |
| node | string | - | Assigned node. |
| cpu_usage_rate | float | CPU seconds/s | Aggregated container CPU usage. |
| memory_working_set_bytes | float | bytes | Aggregated working set memory. |
| memory_rss_bytes | float | bytes | Aggregated RSS memory. |
| cpu_throttled_ratio | float | ratio | Aggregated CPU throttling ratio. |
| network_receive_bytes_rate | float | bytes/s | Aggregated receive network rate. |
| network_transmit_bytes_rate | float | bytes/s | Aggregated transmit network rate. |
| oom_events_total | float | count | Aggregated OOM events. |
| restarts_total | float | count | Aggregated restarts. |

## pod_metadata

Granularity:

```text
pod + namespace
```

Columns:

| Column | Type | Unit | Description |
|---|---:|---:|---|
| pod | string | - | Pod name. |
| namespace | string | - | Kubernetes namespace. |
| node | string | - | Assigned node. |
| controller_kind | string | - | Owner/controller kind. |
| controller_name | string | - | Owner/controller name. |
| qos_class | string | - | Kubernetes QoS class. |
| created_time | float | Unix seconds | Pod creation timestamp. |
| scheduled_time | float | Unix seconds | Pod scheduled timestamp. |
| running_time | float | Unix seconds | Pod running timestamp. |
| ready_time | float | Unix seconds | Pod ready timestamp. |
| succeeded_time | float | scrape timestamp | First scrape where Succeeded phase is observed. |
| failed_time | float | scrape timestamp | First scrape where Failed phase is observed. |

## node_timeseries

Granularity:

```text
timestamp + node
```

Columns:

| Column | Type | Unit | Description |
|---|---:|---:|---|
| timestamp | integer | ms | Prometheus sample timestamp. |
| node | string | - | Node name. |
| cpu_usage_ratio | float | ratio | Derived node CPU usage ratio. |
| memory_used_bytes | float | bytes | Derived used memory. |
| memory_allocatable_bytes | float | bytes | Allocatable memory. |
| cpu_pressure_waiting_seconds_total | float | seconds | CPU pressure waiting time. |
| memory_pressure_waiting_seconds_total | float | seconds | Memory pressure waiting time. |
| memory_pressure_stalled_seconds_total | float | seconds | Memory pressure stalled time. |
| condition_ready | float | boolean-ish | Node ready condition. |
| unschedulable | float | boolean-ish | Node unschedulable status. |
| up | float | boolean-ish | Prometheus `up` metric for node target. |

## node_metadata

Granularity:

```text
node
```

Columns:

| Column | Type | Unit | Description |
|---|---:|---:|---|
| node | string | - | Node name. |
| cpu_allocatable | float | cores | Allocatable CPU. |
| memory_allocatable | float | bytes | Allocatable memory. |
| architecture | string | - | Node architecture. |
| os | string | - | Node operating system. |
| kernel_version | string | - | Kernel version. |
| taints | JSON string | - | Serialized node taints. |
| created_time | float | Unix seconds | Node creation timestamp. |

## controller_timeseries

Granularity:

```text
timestamp + controller_kind + controller_name + namespace
```

Columns:

| Column | Type | Unit | Description |
|---|---:|---:|---|
| timestamp | integer | ms | Prometheus sample timestamp. |
| controller_kind | string | - | Controller kind. |
| controller_name | string | - | Controller name. |
| namespace | string | - | Kubernetes namespace. |
| replicas_desired | float | count | Desired replicas. |
| replicas_ready | float | count | Ready replicas. |

## controller_metadata

Granularity:

```text
controller_kind + controller_name + namespace
```

Columns:

| Column | Type | Unit | Description |
|---|---:|---:|---|
| controller_kind | string | - | Controller kind. |
| controller_name | string | - | Controller name. |
| namespace | string | - | Kubernetes namespace. |
| parent_kind | string | - | Parent controller kind when known. |
| parent_name | string | - | Parent controller name when known. |
| replicas_desired | float | count | Desired replicas when available. |

## Maintenance rule

When an analysis script adds, removes, or renames a column, this document must be updated in the same merge request.

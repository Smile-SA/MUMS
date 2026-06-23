# Refined CSV Schema Reference

This document describes the current refined CSV dataset families.

The exact column set must be kept synchronized with the analysis scripts under `observability/analysis/`.

## container_timeseries

Granularity:

```text
timestamp + namespace + pod + container
```

Expected content:

- CPU usage/rate fields.
- Memory usage fields.
- Network receive/transmit fields when available.
- Restart/OOM/throttling-related fields when available.

## container_metadata

Granularity:

```text
namespace + pod + container
```

Expected content:

- image
- resource requests
- resource limits
- stable container identity fields

## pod_timeseries

Granularity:

```text
timestamp + namespace + pod
```

Expected content:

- aggregated CPU/memory/network metrics from containers
- pod-level derived resource behavior

## pod_metadata

Granularity:

```text
namespace + pod
```

Expected content:

- assigned node
- controller owner
- QoS class
- lifecycle timestamps where available

## node_timeseries

Granularity:

```text
timestamp + node
```

Expected content:

- node CPU/memory behavior
- node readiness or pressure indicators where available

## node_metadata

Granularity:

```text
node
```

Expected content:

- allocatable CPU
- allocatable memory
- labels
- taints
- OS/kernel information where available

## controller_timeseries

Granularity:

```text
timestamp + namespace + controller_kind + controller_name
```

Expected content:

- desired replicas
- ready replicas

## controller_metadata

Granularity:

```text
namespace + controller_kind + controller_name
```

Expected content:

- owner relationships
- controller hierarchy information

## Maintenance rule

When an analysis script adds, removes or renames a column, this document must be updated in the same merge request.

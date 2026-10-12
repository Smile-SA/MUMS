# basic-evaluation

Post-processing module: summarizes one run in a few comparable indicators
(response times, errors, node usage and balance, availability), computed from
standard data only. Writes them in the standard summary format, so that any
comparison can use them without knowing what they mean.

## Actions

- `run <data_dir>`: reads the data below and writes
  `<data_dir>/summary/basic-evaluation.csv`.

## Arguments

| Argument | Default | Description |
|---|---|---|
| `run_window` | `true` | Only count data inside the run window (`run-window`), i.e. while every module was running. With `false`, or without `run-window` data, all the data is counted. |
| `node_metrics` | `true` | Report the `node_*` indicators. Set `false` when nodes share one machine (e.g. kind): node-level metrics then describe the host, identical for every node. Use `pod-based-node-evaluation` there instead. |
| `namespaces` | all | Comma-separated namespaces whose Deployments count in `availability_*`, e.g. the application's. Otherwise the platform's own Deployments (Prometheus, MetalLB, CoreDNS...) and the optimizer's count too, and they differ from one optimizer to another. |

## Data consumed

| Format | Used for |
|---|---|
| `http-requests` | requests, response times, errors |
| `essential-tables` (`node_timeseries`, `node_metadata`, `controller_timeseries`) | node usage, availability |
| `run-window` | the window, with `run_window: true` |

Each one is optional: its indicators are simply absent if it is missing.

## Data produced: `summary`

`<data_dir>/summary/basic-evaluation.csv`, one row per indicator:
`metric, value, unit, goal, description`. `goal` is the indicator's intent:
`minimize`, `maximize` or `none`. Units: `seconds`, `ratio`, `count` (anything
counted), `count/second`.

| Metric | Goal | Definition |
|---|---|---|
| `duration` | none | seconds over which requests are counted (the run window, or first to last request) |
| `requests`, `requests_per_second` | none | requests sent; depends on the load shape |
| `latency_mean_seconds`, `latency_p50_seconds`, `latency_p95_seconds`, `latency_p99_seconds`, `latency_max_seconds` | minimize | response times of the requests that got a response |
| `server_error_rate`, `client_error_rate` | minimize | share of requests answered with a 5xx / 4xx status |
| `no_response_rate` | minimize | share of requests without any response |
| `no_response_<reason>_rate` | minimize | the same, per reason (`timeout`, `connection_refused`, `connection_reset`, `other`) |
| `nodes` | none | nodes taking workload: those without `NoSchedule` / `NoExecute` taint |
| `node_cpu_usage_mean`, `node_memory_usage_mean` | none | mean usage of these nodes' machines |
| `node_cpu_usage_max`, `node_memory_usage_max` | minimize | highest usage of one of their machines |
| `node_cpu_imbalance_mean`, `node_memory_imbalance_mean` | minimize | mean standard deviation of usage across them |
| `node_overload_time_ratio` | minimize | share of time with one of them above 90 % of its machine's CPU or memory |
| `availability_mean`, `availability_min` | maximize | ready / desired replicas of Deployments (capped at 1) |

A node's usage comes from node-level metrics (`node_timeseries`): the CPU usage
of its machine, and memory used / total memory of its machine. Nodes are
measured at different instants: at regular instants (every typical sample
spacing), each node contributes its latest measure, if less than 1.5 spacing old.

## Dependencies

python3.

## Files

`run.sh` (action), `evaluate.py` (computations), `module.yaml`.

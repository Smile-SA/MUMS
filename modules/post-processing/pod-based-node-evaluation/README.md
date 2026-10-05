# pod-based-node-evaluation

Post-processing module: summarizes the **Kubernetes part** of the nodes' usage.
A node's usage is the sum of its pods' usage, against its allocatable (what
Kubernetes may give to pods). Meant for nodes whose machine does more than run
that node (e.g. several nodes on one host), where node-level metrics describe
the machine rather than the node.

## Actions

- `run <data_dir>`: writes `<data_dir>/summary/pod-based-node-evaluation.csv`.

## Arguments

| Argument | Default | Description |
|---|---|---|
| `run_window` | `true` | Only count data inside the run window (`run-window`). With `false`, or without `run-window` data, all the data is counted. |

## Data consumed

| Format | Used for |
|---|---|
| `essential-tables` (`pod_timeseries`, `node_metadata`) | pods' usage, nodes' allocatable and taints |
| `run-window` | the window, with `run_window: true` |

## Data produced: `summary`

`<data_dir>/summary/pod-based-node-evaluation.csv`, one row per
indicator: `metric, value, unit, goal, description`.

| Metric | Goal | Definition |
|---|---|---|
| `nodes` | none | nodes taking workload: those without `NoSchedule` / `NoExecute` taint |
| `node_cpu_usage_mean`, `node_memory_usage_mean` | none | mean usage of these nodes |
| `node_cpu_usage_max`, `node_memory_usage_max` | minimize | highest usage of one of them |
| `node_cpu_imbalance_mean`, `node_memory_imbalance_mean` | minimize | mean standard deviation of usage across them |
| `node_overload_time_ratio` | minimize | share of time with one of them above 90 % of its CPU or memory allocatable |

Usage = sum of the node's pods' usage (`pod_timeseries`) / its allocatable
(`node_metadata`). Pods are measured at different instants: at regular instants
(every typical sample spacing), each pod contributes its latest measure, if less
than 1.5 spacing old.

## Dependencies

python3.

## Files

`run.sh` (action), `evaluate.py` (computations), `module.yaml`.

## Known limitations

- A node so overloaded that its pods are no longer measured looks **less**
  loaded: a pod without a recent measure drops out of the sum. Its usage should
  rather count as unknown at that time.

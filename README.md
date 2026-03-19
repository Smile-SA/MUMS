# Integration Tests

This repository contains a modular architecture to deploy distributed Kubernetes stacks, generate traffic, and test scheduling optimization algorithms.

## Dependencies

**System:**
- `kind`
- `kubectl`
- `helm`
- `docker`
- `git`

**Python (host):**
- `locust`
- `faker`
- `requests`

**Optional:**
- Grafana (local, to visualize metrics)

## Structure
```
tests/
├─ envs/           # Cluster creation/destruction, monitoring and log collection
├─ utils/          # Shared utilities (helm, metallb, prometheus, scraper)
├─ stacks/         # Distributed stacks (deployment)
├─ traffic/        # Traffic generation scripts
│   └─ shapes/     # Reusable load shapes
├─ optimizers/     # Scheduling / optimization algorithms
├─ grafana.sh      # Provision Prometheus datasource in Grafana
└─ run_test.sh     # Main orchestrator
```

- Each stack folder contains: `prepare.sh` (chart download) and `deploy.sh` (cluster deployment).
- Each traffic folder contains: `run.sh` (traffic generation from the host machine).
- "Ready" stacks are directly usable for traffic generation and metrics collection.
- "Framework" stacks require additional configuration to produce real traffic (Kafka, Flink, Spark).

## Script types and specifications

| Script type    | Description                                                   | Expected parameters |
|----------------|---------------------------------------------------------------|---------------------|
| **env**        | Create/destroy a cluster, collect logs                        | `create <seed>` → returns KUBECONFIG <br> `destroy <seed>` |
| **stack**      | Deploy a distributed application on the cluster               | `<KUBECONFIG> <SEED>` |
| **traffic**    | Generate realistic traffic from the host machine              | `<KUBECONFIG> <SEED>` |
| **optimizer**  | Deploy and run a scheduling/optimization algorithm            | `<KUBECONFIG> <SEED>` |

> All scripts accept additional options via `$@` and may ignore those that don't concern them.

## Running a test
```bash
./run_test.sh <env_script> <stack_script> <traffic_script> <optimizer_script> <output_dir> [seed] [options ...]
```

- `$env_script` : creates/destroys the cluster
- `$stack_script` : deploys the stack
- `$traffic_script` : generates traffic from the host machine
- `$optimizer_script` : deploys the optimization algorithm
- `$output_dir` : log and metrics output folder
- `[seed]` : optional, for reproducibility
- `[options ...]` : forwarded to all sub-scripts

## Metrics collection

The `env create` script automatically starts a Prometheus port-forward and a scraper on the host machine. Metrics are written in OpenMetrics format to `<output_dir>/metrics.om` at a configurable frequency.
```bash
./envs/kind.sh create <seed> [--output-dir <path>] [--frequency <seconds>] [--workers "..."]
```

The scraper is stopped and the port-forward is closed on `destroy`.

## Notes

- Traffic is generated from the host machine (outside the cluster) to avoid skewing the resource metrics observed by the optimizer.
- The architecture is modular: new environments, stacks, traffic scenarios, and optimizers can be added independently.
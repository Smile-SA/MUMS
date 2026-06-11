# Benchmark Platform

This repository contains a modular architecture to deploy distributed Kubernetes stacks, generate traffic, collect metrics, and benchmark scheduling optimization algorithms.

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

## Local development setup

Prepare a local Python environment and validate required host tools:

```bash
make setup
make doctor
```

For development checks and test tooling:

```bash
make setup-dev
make check
```

Activate the virtual environment when executing Python tooling manually:

```bash
source .venv/bin/activate
```

Detailed installation and prerequisite information is available in [`docs/setup.md`](docs/setup.md).

## Architecture

The platform is organized around interchangeable benchmark components:

- environment
- application stack
- traffic generator
- observability backend
- optimizer
- dataset/export pipeline

See:

- [`docs/architecture.md`](docs/architecture.md)
- [`docs/components.md`](docs/components.md)

## Script types and conventions

| Script type       | Description                                            | Parameters                                                                   |
| ----------------- | ------------------------------------------------------ | ---------------------------------------------------------------------------- |
| **env**           | Create/destroy a cluster                               | `create <seed>` → returns KUBECONFIG on stdout <br> `destroy <seed>`         |
| **observability** | Start/stop metrics collection (port-forward + scraper) | `start <kubeconfig> <output_dir> [--frequency=<s>]` <br> `stop <kubeconfig>` |
| **stack**         | Deploy a distributed application on the cluster        | `<kubeconfig> <seed>`                                                        |
| **traffic**       | Generate realistic traffic from the host machine       | `start <kubeconfig> <seed>` <br> `stop <kubeconfig>`                         |
| **optimizer**     | Deploy and run a scheduling/optimization algorithm     | `<kubeconfig> <seed>`                                                        |

> All scripts accept additional options via `$@` and ignore those that don't concern them.

## Running a test

```bash
./run_basic_test.sh <env> <observability> <stack> <traffic> <optimizer> <output_dir> [seed] [--duration=<seconds>] [options...]
```

Example:

```bash
./run_basic_test.sh \
  envs/kind.sh \
  observability/prometheus/run.sh \
  stacks/online-boutique/deploy.sh \
  traffic/online-boutique/run.sh \
  optimizers/baseline.sh \
  ./output/test-1 \
  42 \
  --duration=300 \
  --workers "count=4,cpu=1,memory=1Gi;count=2,cpu=1,memory=4Gi"
```

The orchestrator runs the following sequence:

1. `env create` → KUBECONFIG
2. `observability start`
3. `stack deploy`
4. `traffic start`
5. `optimizer deploy`
6. `sleep $DURATION`
7. `observability stop`
8. `traffic stop`
9. `env destroy`

## Notes

- Traffic is generated from the host machine (outside the cluster) to avoid skewing the resource metrics observed by the optimizer.
- The architecture is modular: new environments, stacks, traffic scenarios, and optimizers can be added independently.
- `grafana.sh` must be called with `http://127.0.0.1:9090` (not `localhost` — Grafana DNS cache bug).
- The Python venv must be active before running any test (`source venv/bin/activate`).

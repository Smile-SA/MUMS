# Benchmark Platform

A modular, reproducible benchmark platform for Kubernetes scheduling experiments.
It deploys a distributed application stack, generates realistic traffic, collects
Prometheus metrics, and records a structured dataset — ready for offline analysis
or scheduler evaluation.

## Status

| Component | State |
|-----------|-------|
| Environment — Kind | Supported |
| Stack — Online Boutique | Supported |
| Observability — Prometheus | Supported |
| Traffic — Locust | Supported |
| Optimizer — baseline (no-op) | Supported |
| Dataset export — refined CSV | Supported |
| Connector (apply decisions to cluster) | **Not yet implemented** |
| HOTS / online optimizer | **Not yet implemented** |
| Evaluation / comparison pipeline | **Not yet implemented** |

## Dependencies

**System tools** (must be on `$PATH`):

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

## Setup

```bash
make setup-core          # create .venv and install runtime deps
make setup-dev           # also install dev/lint tools
```

For module-specific dependencies (e.g. Locust extras):

```bash
make setup-module MODULE=traffic/online-boutique
```

To validate required system tools and Python imports:

```bash
make doctor
```

Detailed installation instructions are in [`docs/setup.md`](docs/setup.md).

## Running a benchmark

### 1. Validate your config

```bash
benchmark-platform validate configs/basic-online-boutique.yaml
```

or via Make:

```bash
make validate-config
```

### 2. Run the scenario

```bash
benchmark-platform run configs/basic-online-boutique.yaml
```

or via Make:

```bash
make run-basic
```

The platform runs the following lifecycle sequence:

1. `environment create` → kubeconfig
2. `observability start`
3. `stack deploy`
4. `traffic start`
5. `optimizer deploy`
6. wait `duration_seconds`
7. `observability stop`
8. `traffic stop`
9. `environment destroy`

Run output (metrics, manifest, dataset) lands in `output/runs/<run-id>/`.

### 3. End-to-end smoke test (requires a cluster)

```bash
make smoke
```

## Configuration

Scenarios are described in YAML. Example: [`configs/basic-online-boutique.yaml`](configs/basic-online-boutique.yaml).

Each component section (`environment`, `stack`, `traffic`, …) names a `module:` path
that must contain a `run.sh` and a `module.yaml`. Swap any component by pointing `module:`
at a different directory — no changes to the runner needed.

## Architecture

The platform is organized around interchangeable module families:

- `envs/` — cluster lifecycle (create / destroy)
- `stacks/` — application deployment
- `traffic/` — traffic generation
- `observability/` — metrics collection
- `optimizers/` — scheduling decisions
- `datasets/` — data export and metadata

See [`docs/architecture.md`](docs/architecture.md) and [`docs/components.md`](docs/components.md).

## Adding a module

Each component is a directory containing `run.sh` and `module.yaml`.
See [`docs/writing-a-module.md`](docs/writing-a-module.md) for the full contract,
lifecycle actions, argument conventions, and a worked example.

The script conventions (action names, argument order, stdout/exit contract) are documented
there alongside the `module.yaml` schema.

## Development

```bash
make check      # shell + Python syntax checks
make lint       # Ruff lint (requires make setup-dev)
make test       # Python unit tests (requires make setup-dev)
```

## Notes

- Traffic is generated from the host machine (outside the cluster) to avoid skewing
  resource metrics observed by the optimizer.
- Use `http://127.0.0.1:9090` (not `localhost`) when pointing Grafana at the local
  Prometheus port-forward — Grafana has a DNS cache issue with `localhost`.
- The Python venv must be active for manual CLI invocations (`source .venv/bin/activate`);
  `make` targets activate it automatically.

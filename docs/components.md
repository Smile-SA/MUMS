# Component Lifecycle Contract

## Purpose

This document defines the lifecycle and responsibilities of benchmark
platform components. It is a public contract: modules outside this
repository are written against it, so lifecycle actions listed here as
**REQUIRED** cannot become mandatory-with-a-different-meaning later, and
**OPTIONAL** actions cannot become required, without a scenario-config
version bump (see [`scenario-config.md`](scenario-config.md)).

Every lifecycle action a family supports is either:

- **REQUIRED** — the runner calls it unconditionally; every module of that
  family must implement it.
- **OPTIONAL** — a module declares support for it in `module.yaml`'s
  `lifecycle:` map; the runner only calls it when declared (see
  `ModuleSpec.supports()` in `benchmark_platform/modules.py`). A module that
  omits the `lifecycle:` block entirely is treated as supporting whatever
  it's asked for (back-compat default for modules written before this
  declaration existed).

There are no other, undeclared lifecycle actions in the public contract.
Anything not listed below is out of scope for this release.

## 1. Common conventions

### Inputs

Component adapters accept, directly or indirectly:

- A kubeconfig path when interacting with Kubernetes.
- A seed when randomness is involved.
- An output or run directory when writing artifacts.
- Their own scenario-config section, as opaque JSON in
  `BENCHMARK_COMPONENT_CONFIG` (see [`writing-a-module.md`](writing-a-module.md)).
  The runner does not assemble module-specific CLI flags — every
  module-specific argument is optional and defaulted by the module itself.

### Output behavior

Scripts should:

- Write machine-readable return values to stdout only when the caller needs to capture them.
- Write progress logs and diagnostics to stderr.
- Exit with code `0` on success.
- Exit non-zero on failure.
- Print actionable error messages.

### Long-running behavior

A component that starts a background process uses the log/PID file
locations the runner already provides (`BENCHMARK_LOG_DIR`,
`BENCHMARK_PID_DIR`) and implements `start`/`stop` for its family per the
tables below.

## 2. Environment components

Location:

```text
envs/<env>/
```

Example:

```text
envs/kind/
```

Responsibilities:

- Cluster creation.
- Kubeconfig generation.
- Optional cluster-level infrastructure such as MetalLB and Prometheus.
- Cluster destruction.

Lifecycle:

| Action | Contract | Signature |
|--------|----------|-----------|
| `create` | REQUIRED | `run.sh create <seed>` — must print the kubeconfig path to stdout |
| `destroy` | REQUIRED | `run.sh destroy <seed>` |

## 3. Stack components

Location:

```text
stacks/<stack>/
```

Example:

```text
stacks/online-boutique/
```

Responsibilities:

- Deploy the benchmark application.
- Apply project-specific values.
- Wait for application readiness.
- Return or log the reachable frontend endpoint.

Lifecycle:

| Action | Contract | Signature |
|--------|----------|-----------|
| `deploy` | REQUIRED | `run.sh deploy <kubeconfig> <seed>` |

The runner relies on whole-environment destruction (`environment destroy`)
for stack teardown; there is no `stop`/`destroy` action in the current
contract.

## 4. Observability components

Location:

```text
observability/<backend>/
```

Example:

```text
observability/prometheus/
```

Responsibilities:

- Start or expose monitoring.
- Start raw metrics export.
- Stop monitoring/export processes.
- Write metric artifacts.

Lifecycle:

| Action | Contract | Signature |
|--------|----------|-----------|
| `start` | REQUIRED | `run.sh start <kubeconfig> <metrics_dir>` |
| `stop` | REQUIRED | `run.sh stop <kubeconfig>` (called with `check=False`) |

## 5. Traffic components

Location:

```text
traffic/<target>/
```

Example:

```text
traffic/online-boutique/
```

Responsibilities:

- Resolve the benchmark target endpoint.
- Validate target reachability.
- Start traffic generation.
- Stop traffic generation, if the module runs a long-lived process.

Lifecycle:

| Action | Contract | Signature |
|--------|----------|-----------|
| `start` | REQUIRED | `run.sh start <kubeconfig> <seed>` |
| `stop` | OPTIONAL | `run.sh stop <kubeconfig>` (called with `check=False`, only if declared in `lifecycle:`) |

## 6. Optimizer components

Location:

```text
optimizers/<optimizer>/
```

Examples:

```text
optimizers/baseline/
optimizers/koordinator/
```

Responsibilities:

- Implement or connect the optimization strategy, by deploying onto the
  already-running cluster.
- Run baseline (no-op) behavior when no optimizer is used.

Lifecycle:

| Action | Contract | Signature |
|--------|----------|-----------|
| `deploy` | REQUIRED | `run.sh deploy <kubeconfig>` |

This is intentionally minimal. The optimizer dies with the cluster on
`environment destroy` — the runner never polls its status, and metric
collection is always the observability module's job, never the optimizer's.
`stop`/`status`/`collect` are **not** part of the public contract; an
optimizer that genuinely needs one of them (e.g. a host-side process that
must flush a decision log before exiting) may implement it as an
undeclared, module-specific escape hatch, but it will never be called by the
runner in this release.

## 7. Dataset components

Location:

```text
observability/analysis/     # default: OpenMetrics -> refined CSV
```

The dataset module's default implementation currently lives at
`observability/analysis/` for historical reasons (it grew directly out of
the Prometheus scraper's output) rather than under a `datasets/` directory.
Conceptually it is its own family (`type: dataset`), distinct from
observability — do not treat it as an observability sub-feature when
writing a replacement module.

Responsibilities:

- Turn raw metrics into refined, versioned tables.
- Decide for itself whether there is anything to generate (e.g. skip
  gracefully if the metrics file is missing or empty — do not fail the run).
- Write `datasets/dataset-metadata.yaml` via
  `python3 -m benchmark_platform.datasets.metadata <run_dir>`.

Lifecycle:

| Action | Contract | Signature |
|--------|----------|-----------|
| `generate` | REQUIRED (when the dataset section is enabled) | `run.sh generate <metrics_om_file> <datasets_output_dir>` |

## 8. Module dependencies

A module's `dependencies:` block in `module.yaml` is not a list of things
that are nice to have — it is a list of things that are **installed on
demand for the modules a scenario selects, and required whenever that
module runs**:

```yaml
dependencies:
  python: [requirements.txt]           # installed into the active environment
  commands: [kubectl, helm]            # must exist on PATH
  utils: [utils/scraper]               # recursively resolved
  modules: [observability/prometheus]  # recursively resolved, same as utils
```

`scripts/check_module_deps.sh` and `scripts/install_module_deps.sh` walk
`utils` and `modules` recursively and are the source of truth for how
dependency resolution actually behaves.

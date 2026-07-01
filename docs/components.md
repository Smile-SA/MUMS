# Component Lifecycle Contract

## Purpose

This document defines the expected lifecycle and responsibilities of benchmark platform components.

The first goal is consistency. Components do not need to support every lifecycle action, but unsupported actions must be clear.

## 1. Common conventions

### Inputs

Component adapters should accept, directly or indirectly:

- A kubeconfig path when interacting with Kubernetes.
- A seed when randomness is involved.
- An output or run directory when writing artifacts.
- Component-specific options.
- Environment variables for advanced overrides.

### Output behavior

Scripts should:

- Write machine-readable return values to stdout only when the caller needs to capture them.
- Write progress logs and diagnostics to stderr.
- Exit with code `0` on success.
- Exit non-zero on failure.
- Print actionable error messages.

### Long-running behavior

If a component starts a background process, it should eventually support:

- Explicit log file path.
- Explicit PID file path.
- `start`
- `stop`
- `status`

Issue 5 makes this stricter when run directories are introduced.

## 2. Environment components

Location:

```text
envs/
```

Example:

```text
envs/kind.sh
```

Responsibilities:

- Cluster creation.
- Kubeconfig generation.
- Optional cluster-level infrastructure such as MetalLB and Prometheus.
- Cluster destruction.

Expected lifecycle:

```bash
envs/<env>.sh create <seed> [options]
envs/<env>.sh destroy <seed>
```

Optional future lifecycle:

```bash
envs/<env>.sh status <seed>
envs/<env>.sh collect-state <kubeconfig> <output-dir>
```

## 3. Stack components

Location:

```text
stacks/
```

Example:

```text
stacks/online-boutique/deploy.sh
```

Responsibilities:

- Deploy the benchmark application.
- Apply project-specific values.
- Wait for application readiness.
- Return or log the reachable frontend endpoint.

Current lifecycle:

```bash
stacks/<stack>/deploy.sh <kubeconfig> <seed> [options]
```

Recommended future lifecycle:

```bash
stacks/<stack>/run.sh deploy <kubeconfig> <seed> [options]
stacks/<stack>/run.sh destroy <kubeconfig> <seed> [options]
stacks/<stack>/run.sh status <kubeconfig> <seed> [options]
stacks/<stack>/run.sh endpoint <kubeconfig> <seed> [options]
```

## 4. Observability components

Location:

```text
observability/
```

Example:

```text
observability/prometheus/run.sh
```

Responsibilities:

- Start or expose monitoring.
- Start raw metrics export.
- Stop monitoring/export processes.
- Write metric artifacts.

Current lifecycle:

```bash
observability/<backend>/run.sh start <kubeconfig> <output-dir> [options]
observability/<backend>/run.sh stop <kubeconfig> [options]
```

Recommended future lifecycle:

```bash
observability/<backend>/run.sh status <kubeconfig> [options]
```

## 5. Traffic components

Location:

```text
traffic/
```

Example:

```text
traffic/online-boutique/run.sh
```

Responsibilities:

- Resolve the benchmark target endpoint.
- Validate target reachability.
- Start traffic generation.
- Stop traffic generation.
- Later, collect traffic stats.

Current lifecycle:

```bash
traffic/<target>/run.sh start <kubeconfig> <seed> [options]
traffic/<target>/run.sh stop <kubeconfig> [options]
```

Recommended future lifecycle:

```bash
traffic/<target>/run.sh status <kubeconfig> [options]
traffic/<target>/run.sh collect-stats <kubeconfig> <output-dir> [options]
```

## 6. Optimizer components

Location:

```text
optimizers/
```

Responsibilities:

- Implement or connect the optimization strategy.
- Run baseline behavior when no optimizer is used.
- Start/connect optimizer and collect decision artifacts.

Recommended lifecycle:

```bash
optimizers/<optimizer>/run.sh prepare <run-dir> [options]
optimizers/<optimizer>/run.sh start <run-dir> [options]
optimizers/<optimizer>/run.sh stop <run-dir> [options]
optimizers/<optimizer>/run.sh status <run-dir> [options]
optimizers/<optimizer>/run.sh collect <run-dir> [options]
```

The baseline optimizer may implement these as no-ops.

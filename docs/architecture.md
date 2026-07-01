# Benchmark Platform Architecture

## Purpose

The benchmark platform runs reproducible experiments against time-series-based optimization problems. The current concrete use case is microservice scheduling and resource behavior analysis, using Online Boutique deployed on a local Kind Kubernetes cluster.

The platform is designed around interchangeable components:

```text
Environment
  + Observability
  + Application stack
  + Traffic generator
  + Optimizer
  + Dataset/export pipeline
```

The current supported baseline is:

```text
Kind cluster
  + MetalLB
  + Prometheus
  + Online Boutique
  + host-side Locust traffic
  + Kubernetes default scheduling
  + raw OpenMetrics export
  + refined CSV datasets
```

## Design principle

The benchmark platform orchestrates experiments, but it should not hardcode every environment-specific action in one monolithic runner.

Instead:

- Shell scripts remain valid component adapters.
- A Python runner may orchestrate those adapters.
- Environment-specific logic remains in environment or connector adapters.
- Optimizer should make optimization decisions but should not directly embed all environment-specific execution details.

## Repository responsibilities

```text
envs/
  Environment adapters.
  Example: create/destroy a Kind cluster.

stacks/
  Application stack adapters.
  Example: deploy Online Boutique and expose its frontend.

traffic/
  Traffic generator adapters and traffic profiles.
  Example: run Locust against Online Boutique.

observability/
  Monitoring and metrics collection adapters.
  Example: start Prometheus port-forwarding and collect OpenMetrics.

optimizers/
  Optimizer adapters.
  Exemple: use the default Kubernetes scheduler.

utils/
  Shared helper scripts and vendored deployment utilities.

configs/
  Scenario configuration files.

benchmark_platform/
  Python orchestration package introduced progressively.
  It loads configs, invokes adapters, manages run outputs and writes manifests.

docs/
  User and developer documentation.

tests/
  Unit and smoke tests.
```

## Baseline optimizer meaning

The baseline mode means:

```text
Kubernetes default behavior, with no additional optimizer.
```

## Current data flow

```text
Locust on host
  → Online Boutique frontend exposed by MetalLB
  → Online Boutique services in Kind
  → Prometheus scrapes Kubernetes/workload metrics
  → Host-side scraper writes metrics.om
  → Analysis scripts generate refined datasets
```

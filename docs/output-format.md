# Benchmark Run Output Format

Each config-driven benchmark run creates a self-contained directory.

Example:

```text
output/runs/<run-id>/
├── config.yaml
├── manifest.yaml
├── logs/
├── runtime/
│   ├── pids/
│   └── kubeconfig
├── traffic/
├── metrics/
│   └── metrics.om
├── kubernetes/
├── datasets/
└── artifacts/
    ├── envs.kind/
    ├── stacks.online-boutique/
    ├── observability.prometheus/
    ├── traffic.online-boutique/
    ├── optimizers.baseline/
    └── datasets.refined-csv/
```

## Ownership

| Directory | Owner | Notes |
|-----------|-------|-------|
| `config.yaml` | runner | copy of the executed scenario config |
| `manifest.yaml` | runner | machine-readable run metadata (see below) |
| `logs/` | runner | per-action logs captured by the runner |
| `runtime/` | runner | PID files and the kubeconfig copy |
| `traffic/` | traffic module | Locust CSV statistics (legacy fixed path) |
| `metrics/` | observability module | raw metric collection artifacts (legacy fixed path) |
| `kubernetes/` | runner | best-effort Kubernetes state captured before cleanup |
| `datasets/` | dataset module | refined offline datasets + `dataset-metadata.yaml` (legacy fixed path) |
| `artifacts/<module-name>/` | that module | namespaced directory exposed to every module via `BENCHMARK_ARTIFACT_DIR`, for anything that doesn't fit the fixed directories above |

`logs/` and `runtime/` are always framework-owned. `traffic/`, `metrics/`,
and `datasets/` are today's fixed, module-specific directories — kept as-is
for backward compatibility with existing analysis tooling. New modules, or
new artifact kinds from existing modules, should use their
`artifacts/<module-name>/` directory (via `BENCHMARK_ARTIFACT_DIR`) rather
than inventing another fixed top-level directory, so the core does not need
to keep learning about new module-specific output kinds.

## manifest.yaml

Machine-readable run metadata:

- run ID
- scenario name
- seed
- status
- start/end timestamps
- artifact locations
- environment settings
- optimizer type
- lifecycle events

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

## Optional artifact conventions

Core tooling (`compare`, `provenance.py`) never hardcodes knowledge of any
specific module. Instead, a module may opt into these conventions inside its
own `artifacts/<module-name>/` directory, and core tooling picks them up
generically:

| File | Written by | Read by | Format |
|------|------------|---------|--------|
| `moves.jsonl` | any optimizer module that makes placement decisions | `benchmark_platform/compare.py` | one JSON object per line: `{"old_host": ..., "new_host": ..., "time": ...}`. `old_host: null` marks an initial placement, not a migration, and is excluded from the migration count. |
| `provenance-notes.json` | any module | `benchmark_platform/provenance.py` | a JSON list of caveat strings, aggregated into `manifest.yaml`'s `provenance.notes` |

`compare` finds the right `artifacts/<name>/moves.jsonl` by reading the
optimizer module's name from the run's own `manifest.yaml`
(`modules.optimizer.name`) — it never assumes which optimizer produced a
run. `optimizers/hots/` is the current example implementing both
conventions (`record_moves.py` writes `moves.jsonl`; `run.sh stop` writes
`provenance-notes.json`).

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
- `provenance` (best-effort; never fails the run -- see
  `benchmark_platform/provenance.py`):
  - `image_digests`: container image digests observed in the cluster
    (namespace/pod/container/image_id), from `kubernetes/pods.yaml`
  - `chart_versions`: Helm release name/chart/app_version, via `helm list`
  - `tool_versions`: local `kubectl`/`helm`/`kind`/`docker` versions
  - `notes`: a generic caveat when `output.cleanup_environment: false`
    (this environment persists across runs), plus whatever any module
    contributed via its own `provenance-notes.json` (see "Optional
    artifact conventions" above)

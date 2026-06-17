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
└── datasets/
```

## config.yaml

Copy of the scenario configuration that was executed.

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

## logs/

Component logs captured by the runner.

## runtime/

Runtime files such as PID files and the kubeconfig copy.

## traffic/

Traffic-generator artifacts such as Locust CSV statistics.

## metrics/

Raw metric collection artifacts.

## kubernetes/

Best-effort Kubernetes state captured before cleanup.

## datasets/

Refined offline datasets generated from raw metrics.

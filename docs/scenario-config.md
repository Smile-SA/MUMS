# Scenario Configuration

Benchmark scenarios are described with YAML files.

The first supported config version is `version: 1`.

## Example

See:

```text
configs/basic-online-boutique.yaml
```

## Duration fields

`scenario.duration_seconds` is the total benchmark runtime.

`traffic.cycle_minutes` is the duration of the Locust traffic-shape cycle.

These fields are intentionally separate to avoid the previous ambiguity around `--duration`.

## Currently supported values

```text
environment.type: kind
stack.type: online-boutique
observability.type: prometheus
traffic.type: locust
optimizer.type: baseline
```

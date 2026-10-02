# Scenario Configuration

Benchmark scenarios are described with YAML files.

The first supported config version is `version: 1`.

## Example

See:

```text
configs/basic-online-boutique-1min.yaml
```

## Compatibility policy

The scenario-config format is a stable public contract, decoupled from any
single runner implementation. It is versioned so that a future `main` (or a
future runner rewrite) cannot silently break existing configs and
third-party modules:

- **Version `1` is frozen.** Only additive changes are made to it (new
  optional fields, new component families). Existing required fields never
  change meaning.
- **Breaking changes bump the version.** Anything that would change the
  meaning of an existing field, remove a field, or change how a section is
  interpreted ships as `version: 2` (or later), with the old version still
  supported by `load_config` until it is explicitly deprecated.
- **The core only validates the framework-level envelope**: `version`,
  `scenario.*`, `output.*`, and — per component section — `type` and the
  optional `module` key. Everything else inside a component section (e.g.
  `traffic.shape`, `observability.frequency_seconds`) is opaque to the core
  and validated by the selected module's own `args:` schema in its
  `module.yaml` (see [`writing-a-module.md`](writing-a-module.md) and
  `benchmark_platform/schema.py`).

The top-level envelope shape (sections + `type` + `module`, not per-module
keys) is described as a JSON Schema in
[`schemas/scenario-config.schema.json`](schemas/scenario-config.schema.json).

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
optimizer.type: baseline | koordinator
```

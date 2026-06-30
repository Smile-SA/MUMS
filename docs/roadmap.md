# Roadmap

This document tracks planned features and known future work.
For the current implementation status, see the [README](../README.md#status).

## Future stacks

The following stacks have been prototyped and are candidates for promotion to
full modules (each requires a `run.sh`, `module.yaml`, matching traffic generator,
and observability tuning before being listed as supported):

| Stack | Helm chart | Helm repo |
|-------|-----------|-----------|
| Mattermost | `mattermost/mattermost` | https://helm.mattermost.com |
| OpenTelemetry demo | `open-telemetry/opentelemetry-demo` | https://open-telemetry.github.io/opentelemetry-helm-charts |
| Saleor | `saleor/saleor` | https://helm.saleor.io |
| Sock Shop | `sock-shop/sock-shop` | https://microservices-demo.github.io/helm-charts |

## Planned Phase 2 (reproducibility hardening)

- Pin all images and charts by digest
- Internal registry + external egress blocking during runs
- Deterministic traffic replay from a seeded request schedule
- Full provenance in manifest (git SHA, config hash, tool versions)
- Run isolation by run-id (parallel clusters with same seed)
- Measurement window markers (`measurement.start` / `measurement.stop`)

## Planned Phase 3 (HOTS integration)

- Connector family (`connectors/`) — apply scheduler decisions to the cluster
- Evaluation family (`evaluation/`) — score KPIs, compare baseline vs optimizer
- HOTS offline mode — consume datasets, emit decisions, no live cluster needed
- HOTS online closed-loop — connector applies decisions, platform re-observes

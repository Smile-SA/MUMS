# Changelog

All notable changes to this project are listed here. Versions follow
[Semantic Versioning](https://semver.org); the module contract has its own version
(`contract: 1`), changed only by a new contract.

## [0.1.0] - 2026-10-12

First public release.

- Core: scenarios (`validate`, `run`), module contract 1 (environment, stack,
  observability, traffic, optimizer, disruption, post-processing), discovery of
  modules and utils by name, per-installation settings (`config`, `exec`),
  dependency installation and checks (`deps`), `doctor`, registry of
  environments (`env list`, `env clean`), provenance of every run.
- Comparison of runs from their summaries (`compare`), single runs or groups of
  repetitions with a significance test; `scripts/campaign.py` for repeated runs.
- Modules: kind, prometheus-live-scraper, online-boutique-v0.10.1,
  online-boutique-locust, no-optimization, koordinator and hots (both
  experimental: not stable yet), no-disruption,
  essential-tables, basic-evaluation, pod-based-node-evaluation,
  reference-comparison. Utils: helm, metallb, kafka, compare.

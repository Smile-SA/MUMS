# Benchmark platform

Checks whether a Kubernetes optimizer (a scheduler, a descheduler, an
autoscaler...) works **in a real cluster**: a real application, real traffic, real
metrics, observed while the system runs. It runs experiments in the same conditions,
records what produced their results, and compares optimizers on operational measures:
latency, errors, node usage, disruptions.

A small core runs scenarios; interchangeable modules do the rest: create the
cluster, deploy the application, send traffic, run the optimizer, measure, evaluate.
Adding an optimizer, an application or a cluster provider means writing a module.

## Quick start

On Linux, with Python 3.10+, `kubectl`, `git` and a running Docker:

```bash
./benchmark_platform/bootstrap.sh                                    # from the repository; then open a new terminal
benchmark-platform deps install --scenario configs/smoke-test.yaml
benchmark-platform run configs/smoke-test.yaml                       # one minute, end to end
```

Then measure and compare two optimizers:

```bash
benchmark-platform deps install --scenario configs/koordinator-online-boutique-15min.yaml
benchmark-platform run configs/baseline-online-boutique-15min.yaml
benchmark-platform run configs/koordinator-online-boutique-15min.yaml
benchmark-platform compare output/runs/baseline-online-boutique-15min-* output/runs/koordinator-online-boutique-15min-*
```

## Documentation

| | |
|---|---|
| **Learn** | [Your first benchmark](docs/tutorials/first-benchmark.md) · [Your first module](docs/tutorials/first-module.md) |
| **Do** | [Running benchmarks](docs/guides/running-benchmarks.md) · [Writing modules](docs/guides/writing-modules.md) · [Troubleshooting](docs/guides/troubleshooting.md) |
| **Look up** | [Commands](docs/reference/cli.md) · [Scenarios](docs/reference/scenario.md) · [Module contract](docs/reference/module-contract.md) · [Data formats](docs/formats/README.md) · [Run directory](docs/reference/run-directory.md) · [Settings and installation](docs/reference/settings.md) |
| **Understand** | [Concepts](docs/explanation/concepts.md) · [Design](docs/explanation/design.md) |
| **Modules** | [Catalogue](docs/modules.md) |

Contributing to the core: [CONTRIBUTING.md](CONTRIBUTING.md).

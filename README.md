# mums

**M**icroservices **U**nified **M**easurement **S**imulation: a benchmark platform
for Kubernetes optimizers.

Checks whether a Kubernetes optimizer (a scheduler, a descheduler, an
autoscaler...) works **in a real cluster**: a real application, real traffic, real
metrics, observed while the system runs. It runs experiments in the same conditions,
records what produced their results, and compares optimizers on operational measures:
latency, errors, node usage, disruptions.

A small core runs scenarios; interchangeable modules do the rest: create the
cluster, deploy the application, send traffic, run the optimizer, measure, evaluate.
Adding an optimizer, an application or a cluster provider means writing a module.

## Quick start

On Linux, with Python 3.11+, `kubectl`, `git` and a running Docker:

```bash
./mums/bootstrap.sh       # from the repository; own venv by default, options: --help
                          # then open a new terminal
mums deps install --scenario configs/smoke-test.yaml
mums run configs/smoke-test.yaml       # one minute, end to end
```

Then measure and compare two optimizers:

> The `koordinator` and `hots` optimizer modules are **experimental**: installing
> and using them is not stable yet (see [the catalogue](docs/modules.md)). The
> Koordinator run below may fail at `[optimizer] start`.

```bash
mums deps install --scenario configs/koordinator-online-boutique-15min.yaml
mums run configs/baseline-online-boutique-15min.yaml
mums run configs/koordinator-online-boutique-15min.yaml
mums compare output/baseline-online-boutique-15min-* output/koordinator-online-boutique-15min-*
```

## Documentation

| | |
|---|---|
| **Learn** | [Your first benchmark](docs/tutorials/first-benchmark.md) · [Your first module](docs/tutorials/first-module.md) |
| **Do** | [Running benchmarks](docs/guides/running-benchmarks.md) · [Writing modules](docs/guides/writing-modules.md) · [Writing utils](docs/guides/writing-utils.md) · [Troubleshooting](docs/guides/troubleshooting.md) |
| **Look up** | [Commands](docs/reference/cli.md) · [Scenarios](docs/reference/scenario.md) · [Module contract](docs/reference/module-contract.md) · [Data formats](docs/formats/README.md) · [Run directory](docs/reference/run-directory.md) · [Settings and installation](docs/reference/settings.md) |
| **Understand** | [Concepts](docs/explanation/concepts.md) · [Design](docs/explanation/design.md) |
| **Modules** | [Catalogue](docs/modules.md) |

Contributing to the core: [CONTRIBUTING.md](CONTRIBUTING.md).

## Credits

Authors:

- Timon Roxard
- Etienne Leclercq
- Jonathan Rivalan
- Smile R&D

## License

This software is provided under the terms of the Apache license, version 2.0, you can read in the
`LICENSE.txt` file of the repository or the package.
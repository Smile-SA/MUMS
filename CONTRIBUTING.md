# Contributing

Thank you for your interest in contributing!

## Adding a module

The fastest way to contribute is to add a module: an environment, an application
stack, a traffic generator, an observability backend, an optimizer, a
post-processing step. A module is a self-contained directory, independent of the
core: see [Your first module](docs/tutorials/first-module.md),
[Writing modules](docs/guides/writing-modules.md) and the
[module contract](docs/reference/module-contract.md).

The rest of this file is about the core: the `mums` package, which
runs scenarios and knows nothing of any specific module.

## Setup

From the repository's directory:

```bash
./mums/bootstrap.sh --dev      # also installs the test and lint tools
```

## Checks

| Command | What it does |
|---|---|
| `make test` | the tests (pytest), core and modules |
| `make lint` | lint (Ruff) of the core, the tests, the modules and the utils |
| `make check` | syntax of every shell and Python file |
| `make smoke-test` | a real one-minute run, end to end (needs Docker) |

`make help` lists the other targets (installation, cleanup). `make lint` and
`make test` run in the platform's environment, through `mums exec`.

## Organization of the core

| File | Role |
|---|---|
| `cli.py` | the `mums` command |
| `settings.py` | the settings: configuration file, variables, applied at the start of every command |
| `discovery.py` | finds modules and utils, by name |
| `config.py`, `schema.py` | the scenario format, and modules' arguments |
| `modules.py` | the module contract: types, actions, descriptor validation |
| `dependencies.py` | dependency checks and installs, recursively |
| `runner.py` | runs a scenario, step by step |
| `paths.py`, `manifest.py` | a run's directory, its manifest |
| `provenance.py` | what produced a run's results |
| `cleanup.py` | the registry of environments, `env clean` |
| `doctor.py` | `mums doctor` |
| `shell.py`, `warn.py` | running commands, warnings |
| `bootstrap.sh` | installation |

## Tests

- Core tests (`tests/`) use fake modules, created by the fixtures of
  `tests/conftest.py`: they never need a cluster, and never read the
  installation's configuration file.
- A module's own tests live in its directory (`<module>/tests/`).
- Every change to the core comes with its tests.

## Rules

- **The core knows no specific module.** No tool or module name in
  `mums/`: `grep -rniE "kind|helm|prometheus|online-boutique|locust|hots|no-optimization|no-disruption|koordinator" mums/`
  must only find justified occurrences.
- **Side tasks never fail a run** (provenance, state collection): they record
  their errors and go on.
- **The module contract** ([reference](docs/reference/module-contract.md)) is
  frozen once published: any change to it is a new contract version.

See [the design](docs/explanation/design.md) for the principles behind these rules.

## Code style

- **Python**: linted with [Ruff](https://docs.astral.sh/ruff/) (`make lint`), line
  length 100.
- **Shell**: syntax checked with `bash -n` (`make check`); scripts start with
  `set -euo pipefail`.
- **Language**: English only in every shipped file.

## Submitting changes

1. Fork the repository, and create a branch for your change from `dev`.
2. Make your change; run `make check`, `make lint` and `make test` before pushing.
3. Open a pull request, and fill in its template. A maintainer reviews it within a
   few days.

Commit messages say what changed and why.

## Reporting bugs

Use the issue tracker, and fill in the bug report template: steps to reproduce,
expected and actual behaviour, your environment (OS, Docker, kubectl and kind
versions). `mums doctor` gives most of it.

## License

By contributing, you agree that your contributions are licensed under the
[Apache-2.0 license](LICENSE).

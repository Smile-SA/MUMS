# Contributing to the core

The core is the `benchmark_platform` package: it runs scenarios and knows nothing
of any specific module. Modules and utils have their own READMEs; writing one is
covered in [the docs](docs/guides/writing-modules.md).

## Setup

```bash
./benchmark_platform/bootstrap.sh --dev      # also installs the test and lint tools
```

## Checks

| Command | What it does |
|---|---|
| `make test` | the tests (pytest), core and modules |
| `make lint` | lint (ruff) of the core, the tests, the modules and the utils |
| `make check` | syntax of every shell and Python file |
| `make smoke-test` | a real one-minute run, end to end (needs Docker) |

`make help` lists the other targets (installation, cleanup). `make lint` and
`make test` run in the platform's environment, through `benchmark-platform exec`.

## Organization of the core

| File | Role |
|---|---|
| `cli.py` | the `benchmark-platform` command |
| `settings.py` | the settings: configuration file, variables, applied at the start of every command |
| `discovery.py` | finds modules and utils, by name |
| `config.py`, `schema.py` | the scenario format, and modules' arguments |
| `modules.py` | the module contract: types, actions, descriptor validation |
| `dependencies.py` | dependency checks and installs, recursively |
| `runner.py` | runs a scenario, step by step |
| `paths.py`, `manifest.py` | a run's directory, its manifest |
| `provenance.py` | what produced a run's results |
| `cleanup.py` | the registry of environments, `env clean` |
| `doctor.py` | `benchmark-platform doctor` |
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
  `benchmark_platform/`: `grep -rniE "kind|helm|prometheus|online-boutique|locust|hots|baseline|koordinator" benchmark_platform/`
  must only find justified occurrences.
- **Side tasks never fail a run** (provenance, state collection): they record
  their errors and go on.
- **The module contract** ([reference](docs/reference/module-contract.md)) is
  frozen once published: any change to it is a new contract version.

See [the design](docs/explanation/design.md) for the principles behind these rules.

## Workflow

One branch per topic, from `dev`, merged back into `dev`. Commit messages say what
changed and why.

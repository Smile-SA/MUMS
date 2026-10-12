# Command line: `mums`

Every command first applies the installation's settings (see
[settings.md](settings.md)), except `config`, which reads and edits them.

| Command | Purpose |
|---|---|
| [`run`](#run) | run a scenario |
| [`validate`](#validate) | check a scenario without running it |
| [`deps`](#deps) | install or check the dependencies of modules and utils |
| [`compare`](#compare) | compare runs from their summaries |
| [`env`](#env) | list or destroy environments left by runs |
| [`doctor`](#doctor) | overview of the machine and of the platform |
| [`config`](#config) | show or change the settings |
| [`exec`](#exec) | run any command in the platform's environment |

## `run`

```text
mums run <scenario.yaml> [-v | -q]
```

Validates the scenario (as [`validate`](#validate) does), then runs it and prints
its directory. The steps are shown as they go; see
[concepts](../explanation/concepts.md#a-run-step-by-step) for their order.

| Option | Effect |
|---|---|
| `-v`, `--verbose` | also show the modules' output |
| `-q`, `--quiet` | show nothing but errors and the run's directory |

## `validate`

```text
mums validate <scenario.yaml>
```

Checks a scenario without running anything: the platform's own prerequisites
(`kubectl`), the scenario's format, that each module exists
and has the expected type, the arguments given to each module (against its
descriptor), and the dependencies of all modules and their utils. Unknown fields
are reported as warnings.

## `deps`

```text
mums deps install <name>... | --all | --scenario <scenario.yaml>
mums deps check   <name>... | --all | --scenario <scenario.yaml>
```

Installs or checks the dependencies of modules and utils, recursively: a
module's utils first, each one once. `install` runs every dependency script's
`install`, then checks everything.

| Selection | Modules and utils concerned |
|---|---|
| `<name>...` | the ones named |
| `--all` | every module and util found; a failure does not stop the others, all failures are reported at the end |
| `--scenario <file>` | the modules of a scenario |

## `compare`

```text
mums compare <run>... [-v] [-m [FILE]] [-c [FILE]]
mums compare -g <name> <run>... -g <name> <run>... [--alpha A] [-v] [-m [FILE]] [-c [FILE]]
```

Compares runs from their summaries. Takes run directories (glob patterns accepted)
and hands their data directories to the util `compare`; see its README for the
report.

- **Single runs**: the first run is the reference; each indicator's change and
  better / worse verdict, without significance test.
- **Groups** (`-g`, repeated): repetitions of each configuration; the first group
  is the reference. Each indicator's median and interquartile range per group, and
  a verdict only when the difference is significant (Mann-Whitney U, p < `--alpha`,
  default 0.05).

| Option | Output |
|---|---|
| `-v`, `--verbose` | aligned report on the console (the default without option) |
| `-m`, `--markdown [FILE]` | Markdown report (default file: `comparison.md`) |
| `-c`, `--csv [FILE]` | every value in long form (default file: `comparison.csv`) |

## `env`

```text
mums env list
mums env clean <environment_id> [-v]
mums env clean-all [-v]
```

A run registers its environment before creating it, and unregisters it once
destroyed. An environment still registered was left by a run that was
interrupted, kept on purpose (`output.cleanup_environment: false`), or whose
destruction failed.

| Command | Effect |
|---|---|
| `list` | the registered environments |
| `clean <id>` | destroys one, through its environment module (`-v`: show the module's output) |
| `clean-all` | destroys them all |

## `doctor`

```text
mums doctor
```

Informative overview, checks nothing: the Python interpreter, the core's
prerequisites, the settings and where each comes from, the platform's git state,
the dependencies of every module and util found, the registered environments.

## `config`

```text
mums config [show]
mums config path
mums config get <setting>
mums config set <setting> <value>...
mums config add module_paths <path>...
mums config remove module_paths <path>...
mums config unset <setting>
```

Shows or changes the settings `module_paths`, `utils_path` and `env`; see
[settings.md](settings.md).

| Command | Effect |
|---|---|
| `show` (default) | each setting, its value and where it comes from |
| `path` | the installation's configuration file |
| `get` | one setting's value |
| `set` | writes a setting to the file (`module_paths` takes one or more values) |
| `add` | adds paths to `module_paths` in the file, keeping the others |
| `remove` | removes paths from `module_paths` in the file |
| `unset` | removes a setting from the file |

## `exec`

```text
mums exec -- <command> [<argument>...]
```

Runs a command in the platform's environment, with its settings applied, as the
platform runs modules (e.g. `mums exec -- python3 -m pytest`).

## Exit codes

| Code | Meaning |
|---|---|
| `0` | success |
| `1` | failure: a run that failed, an environment that could not be destroyed, settings that cannot be applied... (`compare`: the util's own code) |
| `2` | invalid input or unmet requirement: scenario, module descriptor, missing or failed dependencies, command line |
| `127` | `exec`: command not found |
| `130` | interrupted (Ctrl+C) |

Messages are prefixed with their kind: `[ERROR]`, `[CONFIG ERROR]` (scenario),
`[MODULE ERROR]` (module or descriptor), `[DEPENDENCY ERROR]`, `[WARNING]`.

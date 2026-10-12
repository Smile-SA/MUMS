# Module contract (version 1)

What a module is, how the platform calls it, and what it must do. This contract
is the interface between the platform and every module: it is frozen once the
platform is published.

## A module

A module is a directory holding a descriptor, `module.yaml`, and the files it
needs. It is found by searching the installation's module directories (see
[settings.md](settings.md)), and designated by its name.

```text
<module>/
├── module.yaml        descriptor (required)
├── README.md          documentation (see "README" below)
├── run.sh             entrypoint: any executable, named in module.yaml
└── dependencies.sh    dependency script (optional), named in module.yaml
```

### `module.yaml`

```yaml
name: online-boutique-locust
type: traffic
contract: 1
entrypoint: run.sh

lifecycle:
  start: "<kubeconfig> <seed> <data_dir>"
  stop: "<kubeconfig>"

args:
  log_dir:
    type: string
    description: "Directory where the module writes its logs."
  shape:
    required: false
    type: string
    description: "Load shape: a file shapes/<shape>.py (default: day_profile)."

dependencies:
  entrypoint: dependencies.sh
  commands:
    - python3
    - kubectl
  utils:
    - helm
```

| Field | Required | Content |
|---|---|---|
| `name` | yes | unique among all modules and utils found |
| `type` | yes | `environment`, `stack`, `observability`, `traffic`, `optimizer`, `disruption` or `post-processing` |
| `contract` | no | the contract version the module follows: `1` (the default) |
| `entrypoint` | yes | the executable called for every action, relative to the module's directory |
| `lifecycle` | yes | the actions the module implements, each with its positional arguments, exactly as in the [table below](#actions) |
| `args` | no | the named arguments the module accepts: see [Arguments](#arguments) |
| `dependencies` | no | see [Dependencies](#dependencies) |
| `description` | no | free text |

Unknown fields are ignored, with a warning.

## Actions

Each type has a fixed set of actions. Required actions must be declared; optional
ones are called only if declared. In `lifecycle`, each action is declared with its
positional arguments, exactly as below.

| Type | Action | Positional arguments | Required |
|---|---|---|---|
| `environment` | `create` | `<seed> <id> <output_file>` | yes |
| | `destroy` | `<id>` | yes |
| `stack` | `deploy` | `<kubeconfig> <seed>` | yes |
| | `delete` | `<kubeconfig>` | no |
| `observability` | `start` | `<kubeconfig> <data_dir>` | yes |
| | `stop` | `<kubeconfig>` | no |
| `traffic` | `start` | `<kubeconfig> <seed> <data_dir>` | yes |
| | `stop` | `<kubeconfig>` | no |
| `optimizer` | `start` | `<kubeconfig>` | yes |
| | `stop` | `<kubeconfig>` | no |
| `disruption` | `start` | `<kubeconfig> <seed>` | yes |
| | `stop` | `<kubeconfig>` | no |
| `post-processing` | `run` | `<data_dir>` | yes |

| Argument | Content |
|---|---|
| `<seed>` | the scenario's seed (positive integer) |
| `<id>` | the environment's id: lowercase letters, digits and `-`, 40 characters at most; the same for `create` and `destroy` |
| `<output_file>` | where `create` writes the path of the cluster's kubeconfig (one line) |
| `<kubeconfig>` | path of the cluster's kubeconfig |
| `<data_dir>` | the run's data directory (absolute path), see [Standard data](#standard-data) |

What each action must do:

- **`environment create`** creates a cluster, and writes the path of its
  kubeconfig to `<output_file>`.
- **`environment destroy <id>`** removes everything that exists for `<id>`, whatever
  is left (a complete, partial or absent environment): it never fails because
  something is missing. It may be called long after the run, by
  `mums env clean`.
- **`start` / `deploy`** launch the module and return once it is running. Anything
  the module leaves running afterwards (a process on the machine) runs in the
  background.
- **`disruption start`** sets the disruptions up and returns: they act in the
  background during the run, at times the module chooses (its arguments). It is
  called right before the traffic starts, so a delay counted from it also includes
  the traffic's start-up.
- **`stop` / `delete`** stop it. They are called for every module that was started,
  even if its start failed half-way, or if a later step failed: they must succeed
  whatever is running (or not).
- **`post-processing run`** reads standard data and writes standard data, then
  returns.

## How an action is called

```text
<entrypoint> <action> <positional arguments> [--<argument> <value>]...
```

For example: `run.sh start /path/kubeconfig 42 /path/data --shape day_profile`.

- **Directory**: the module's own directory. Paths given by the platform are
  absolute.
- **Environment**: the platform's (with its `env` setting applied), plus
  `MUMS_UTILS_PATH`, the directory of the utils.
- **Output**: everything the action prints (standard output and error) goes to
  `logs/<module>/<action>.log` in the run; with `run -v`, also to the terminal.
- **Exit code**: `0` for success, anything else for failure. A failure of a
  launching action stops the run (stops and destruction still happen); a failure
  of a stop, of `destroy` or of a post-processing module is reported, and the run
  goes on.

## Arguments

The `args` of `module.yaml` declares the named arguments the module accepts:

```yaml
args:
  cycle_minutes:
    required: false
    type: positive_int
    description: "Duration of one cycle of the shape (default: 60)."
```

| Key | Content |
|---|---|
| `type` | `string` (not empty), `positive_int`, `bool` or `mapping` |
| `required` | `true` if the scenario must give it (default: `false`) |
| `description` | what it does, and its default value |

The scenario gives the values; the platform checks their type and passes every
given argument to every action, as `--<name> <value>`: a `bool` as `true` or
`false`, a `mapping` as JSON. An argument the scenario does not give is not
passed: **the module applies its own default**, which its description states.

Two arguments are given by the platform, not by the scenario, and only to a
module that declares them (`type: string`, not required): a module asks for one,
both or neither.

| Argument | Content |
|---|---|
| `log_dir` | a directory for what is a log (`logs/<module>/` in the run) |
| `extras_dir` | a directory for everything else that has no other place, notably what is produced to explain or debug a run (internal state, PID files...) (`extras/<module>/` in the run) |

Whatever an action prints goes, in any case, to `logs/<module>/<action>.log`.

## Standard data

Modules exchange data only through **standard formats**, each in its own
directory of the run's data directory: `<data_dir>/<format>/`. A module writes only
the formats it produces, reads those it needs, and knows nothing of who produced
them. Formats are described in [the formats directory](../formats/README.md); it
is not a closed list: a module may create a new format when it needs one.

Everything else a module produces goes to its `extras_dir` or its `log_dir`: it is
for understanding a run, never for evaluating it, and no other module reads it.

## Dependencies

```yaml
dependencies:
  entrypoint: dependencies.sh   # optional
  commands: [python3, kubectl]  # optional
  utils: [helm]                 # optional
```

| Key | Content |
|---|---|
| `commands` | every command the module calls that must already be present in the environment, except bash and POSIX utilities (`sed`, `grep`, `awk`, `cat`, `sleep`, `find`...). `kubectl` included: the platform gives a kubeconfig, not `kubectl`. Commands the dependency script installs into the environment are declared too |
| `utils` | the utils the module calls |
| `entrypoint` | a script taking `install` or `check` |

The dependency script:

- **`install`** installs what the module needs and can be run again safely. It may
  install into the module's own directory (e.g. a virtual environment of the
  module, a `.bin/`): what it installs there is not declared in `commands`.
- **`check`** verifies that everything is in place, quickly and without changing
  anything; it exits with a non-zero code and says what is missing otherwise.
- Both run from the module's directory, in the platform's environment, with
  `MUMS_UTILS_PATH`.

A command needed only in some configurations of the module (e.g. a tool found on
`PATH` in one mode, installed locally in another) is not declared in `commands`:
the `check`, which knows the configuration, verifies it.

Before a run, the platform checks the dependencies of every module of the
scenario and of their utils, recursively, and stops if anything is missing:
`mums deps install` installs them.

## Utils

A util is a directory holding a `util.yaml` and scripts that modules (or the
platform) call. Utils are searched in the installation's utils directory only;
modules call them as `$MUMS_UTILS_PATH/<util>/<script>`.

```yaml
name: helm
dependencies:            # same as a module's
  entrypoint: dependencies.sh
  commands: [helm, curl]
```

| Field | Required | Content |
|---|---|---|
| `name` | yes | unique among all modules and utils found |
| `dependencies` | no | as for a module |
| `description` | no | free text |

## Rules

- **A module knows the platform's vocabulary, not its details.** It may speak of
  scenarios, runs, module types; not of the platform's directories, scenario names,
  or other modules, except the utils it declares.
- **A module never evaluates.** Only observability and post-processing measure a
  run; whatever else a module writes is for understanding it.
- **A process left in the background is detached from the action's output**
  (`> /dev/null 2>&1 < /dev/null`, or its own log file): otherwise the platform
  keeps waiting for that output to close.

## Names

- **A module is named after the tool it integrates**: `kind`, `koordinator`. A
  qualifier is added only to tell variants apart (`prometheus-live-scraper`,
  `online-boutique-locust`), a version only when it defines the module
  (`online-boutique-v0.10.1`; otherwise it is an argument), an author only in case
  of conflict. No type prefix: the type is in the descriptor.
- **Directories**: `modules/<type>/<name>/`, `utils/<name>/`.
- **Files**: `snake_case`.

## README

Every module and util has a `README.md`, with these sections (those that apply):

```text
# <name>

<one paragraph: what it does, with which tool>

## Actions         each action and what it does
## Arguments       a table: argument, default, description (or "None.")
## Data consumed   the standard formats it reads
## Data produced   the standard formats it writes, or "None."
## Extras, logs    what it writes there
## Dependencies    what it needs, and what its dependency script installs
## Files           the module's files
## Known limitations
```

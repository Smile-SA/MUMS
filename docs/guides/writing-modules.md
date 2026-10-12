# Writing modules

Practical advice for writing a module or a util. The contract itself (descriptor,
actions, arguments, dependencies) is in [the reference](../reference/module-contract.md);
a first module is written step by step in [the tutorial](../tutorials/first-module.md).

## Where to put it

Anywhere: add its directory to the installation's module directories.

```bash
mums config add module_paths ~/my-modules
```

Or, for one command only, `MUMS_MODULE_PATHS=~/my-modules:` (the trailing `:`
keeps the installation's directories). By convention, a module goes in
`<directory>/<type>/<name>/`.

## Start from the closest module

Copy a module of the same type, change its name in `module.yaml`, and adapt it.
The type fixes the actions and their arguments; a module of the same type already
parses them.

## Parse the arguments

An action is called as `<entrypoint> <action> <positional arguments> [--<name>
<value>]...`. The positional arguments are fixed by the contract, according to the
module's type ([table](../reference/module-contract.md#actions)); the named
arguments are those the module declares in `args`, given by the scenario, or by
the platform for `log_dir` and `extras_dir`: a module receives these two only if
it declares them ([contract](../reference/module-contract.md#arguments)). Set
every named argument's default first, then read the options, and refuse unknown
ones: they reveal a mismatch with `module.yaml`.

```bash
SHAPE="day_profile"                  # default, stated in module.yaml's description
while [ "$#" -gt 0 ]; do
    case "$1" in
        --log_dir)    LOG_DIR="$2";    shift 2 ;;
        --extras_dir) EXTRAS_DIR="$2"; shift 2 ;;
        --shape)      SHAPE="$2";      shift 2 ;;
        *) echo "ERROR: unknown option '$1'" >&2; exit 1 ;;
    esac
done
```

A `mapping` argument arrives as JSON (read it with `jq` or Python), a `bool` as
`true` or `false`.

## Make stops robust

A `stop`, a `delete` or a `destroy` is called whatever happened before: after a
start that failed half-way, after an interruption, twice. It must succeed in all
these cases:

- record what you start (a PID file in the extras directory, a resource's name),
  and stop only what is recorded;
- treat "already stopped" or "not found" as success;
- `destroy <id>` must work from the id alone: it may be called long after the run,
  by `mums env clean`.

## Leave processes in the background properly

A process that keeps running after the action returns must be detached from the
action's output, otherwise the platform waits for it:

```bash
my-collector --out "$EXTRAS_DIR/collector.log" > /dev/null 2>&1 < /dev/null &
echo $! > "$EXTRAS_DIR/collector.pid"
```

Check that it is still alive before returning, and fail if it died: a module that
silently stopped working is worse than a failed run.

## Write standard data

- Write only the formats you produce, in `<data_dir>/<format>/`, following
  [their description](../formats/README.md).
- Write everything else (internal state, debugging files) in the extras directory.
- A module may create a new format when no existing one fits: see
  [New formats](../formats/README.md#new-formats).

## Declare dependencies

List in `commands` every command the module calls that must already be present
(bash and POSIX utilities excepted, `kubectl` included), and in `utils` the utils
it calls. Install the rest in the dependency script:

```bash
case "${1:-}" in
    install) python3 -m venv .venv && .venv/bin/pip install -r requirements.txt ;;
    check)   .venv/bin/python -c "import locust" || { echo "run: deps install"; exit 1; } ;;
esac
```

Pin versions (`locust==2.46.4`, not `locust>=2.31`): the provenance records what
ran, but only pinned versions run the same next time. A Python module is best kept
in its own virtual environment: its packages then never conflict with other
modules'.

## Use a util

A util is a shared building block: scripts that several modules call (installing a
Helm chart, starting a Kafka broker...). To use one:

1. declare it in `dependencies.utils`: its own dependencies are then checked and
   installed with the module's;
2. call its scripts through `MUMS_UTILS_PATH`, the utils directory every
   action receives:

   ```bash
   "$MUMS_UTILS_PATH/helm/install.sh" "$KUBECONFIG" my-release my-chart 1.2.3
   ```

3. read its README for its scripts and their arguments. The [catalogue](../modules.md)
   lists the available utils.

## Test it

```bash
mums deps install my-module
mums validate configs/my-scenario.yaml
mums run configs/my-scenario.yaml -v
```

`-v` shows the module's output; it is also in `logs/<module>/<action>.log` in the
run. Run an action by hand from the module's directory, with the arguments shown
in the log, to debug it.

## Write a util

When several modules need the same thing, make it a util: see
[Writing utils](writing-utils.md).

## Document it

Write the module's README following [the model](../reference/module-contract.md#readme):
what it does, its actions, arguments and defaults, the data it reads and writes,
its extras, dependencies, files and known limitations.

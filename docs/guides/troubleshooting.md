# Troubleshooting

Problems with the platform itself. A module's own problems are in its README.

## `mums: command not found`

The command is linked into `~/.local/bin`, which must be on `PATH`. Open a new
terminal after installing; if it is still missing, check that your shell's profile
puts `~/.local/bin` on `PATH` (the installer adds it, unless `--no-shell-profile`
was given).

## `… is not set` / settings missing

The installation's settings are missing: run `./mums/bootstrap.sh`
again, or set them with `mums config set`. `mums
config` shows each setting and where it comes from: an environment variable
overrides the file, possibly without you knowing.

## Missing dependencies

`mums validate` or `run` stops with `[DEPENDENCY ERROR]` and the
command to run:

```bash
mums deps install --scenario <scenario.yaml>
```

If the installation fails, the message says what to install by hand.
`mums doctor` shows the state of every module and util.

## A run failed

The step that failed is marked `✗`, and its error printed. Then:

- `logs/<module>/<action>.log` in the run holds everything the action printed;
- `manifest.yaml` lists every step, with its times, exit code and error;
- the module's README lists its known problems.

Run the scenario again with `-v` to see the modules' output as it goes.

## An environment was left behind

An interrupted run, or one whose destruction failed, leaves its environment:

```bash
mums env list
mums env clean <id>        # or: env clean-all
```

## `[WARNING] Unknown field(s)`

A field is not recognized: a typo, an argument the module does not declare, or a
field from an older version. It is ignored: check its spelling against the module's
README or [the scenario reference](../reference/scenario.md).

## Results vary between runs

Expected: a few percent between two identical runs, more on small values. Repeat
runs, keep the machine idle, and compare groups of runs. See
[running benchmarks](running-benchmarks.md#repeat-runs).

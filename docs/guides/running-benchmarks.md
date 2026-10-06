# Running benchmarks

How to set up, run and compare benchmarks. For a first walk-through, see
[the tutorial](../tutorials/first-benchmark.md).

## Write a scenario

Start from an existing scenario in `configs/`, and change what the experiment
needs: usually the optimizer, the duration, the load, the cluster's size. The
[catalogue](../modules.md) lists the available modules; each module's README gives
its arguments. The format is in [the reference](../reference/scenario.md).

To compare optimizers, keep everything else identical: same environment, same
application, same traffic, same duration, same seed. Only the `optimizer` section
should differ between the scenarios.

Check a scenario before running it:

```bash
benchmark-platform validate configs/my-scenario.yaml
```

## Install what it needs

```bash
benchmark-platform deps install --scenario configs/my-scenario.yaml
```

This installs the dependencies of the scenario's modules and of their utils, then
checks them. `benchmark-platform doctor` shows the state of every module found.

## Run it

```bash
benchmark-platform run configs/my-scenario.yaml
```

The run's directory is printed first; the steps follow. Keep the machine otherwise
idle during a run: whatever else runs on it competes with the cluster and the load
generator, and skews the measures.

## Repeat runs

Two runs of the same scenario differ by a few percent (more on small values): one
run is not enough to conclude. Run each scenario several times, and compare groups
of runs rather than single runs. With the same seed, the runs differ only by what
the platform does not control; with different seeds, they also cover different
random choices of the modules.

## Compare runs

From their summaries (written by evaluation modules such as `basic-evaluation`):

```bash
benchmark-platform compare output/runs/baseline-* output/runs/koordinator-* -v
```

The first run is the reference. For each indicator, the report gives each run's
value, its change against the reference, and whether it is better or worse,
according to the indicator's goal. A verdict does not account for the variability
between runs: a small change between two single runs means nothing.

To compare within a run, add the module `reference-comparison` at the end of its
post-processing, with the data directory of a reference run:

```yaml
post-processing:
  - module: essential-tables
  - module: basic-evaluation
  - module: reference-comparison
    reference: /absolute/path/to/a/baseline/run/data
```

## Keep an environment

To inspect the cluster after a run, set `output.cleanup_environment: false`. The
environment then stays registered: list it with `benchmark-platform env list`, and
destroy it with `benchmark-platform env clean <id>` once done.

## Check what ran

A run's `provenance/` records what produced its results: the scenario, the
platform's commit and uncommitted changes, a digest of each module and command,
the machine, and the cluster's state at the end of the run. Two runs whose module
digests, commands and images match ran the same code. See
[the reference](../reference/run-directory.md#provenance).

## Share results

A run's provenance holds the cluster's Secrets in clear: remove
`provenance/kubernetes/secrets.yaml`, or check it, before sharing a run.

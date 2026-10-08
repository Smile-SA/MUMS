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
of runs rather than single runs. Repeating with the same seed measures the
variability due to the environment; changing the seed also covers other random
choices of the modules.

`scripts/campaign.py` does it: it runs every scenario once per round, in an order
shuffled in each round, with the round's seed (the scenario's seed + the round's
index), and puts all the runs in one directory:

```bash
benchmark-platform exec -- python3 scripts/campaign.py -n 5 \
    configs/baseline-online-boutique-15min.yaml \
    configs/koordinator-online-boutique-15min.yaml
```

At the end, it prints the `compare` command for its runs. Keep the machine idle
during a campaign.

## Compare runs

From their summaries (written by evaluation modules such as `basic-evaluation`).
Groups of repetitions, the first one being the reference:

```bash
benchmark-platform compare -m report.md \
    -g baseline 'output/campaign-…/baseline-online-boutique-15min-*' \
    -g koordinator 'output/campaign-…/koordinator-online-boutique-15min-*'
```

For each indicator, the report gives each group's median and interquartile range,
the change of medians against the reference, and ✓ / ✗ only when the difference is
significant (two-sided Mann-Whitney U test, p < 0.05, `--alpha` to change it); `~`
otherwise. With 3 runs per group, nothing can be significant: run at least 5.

Single runs can be compared too (`benchmark-platform compare <run> <run>...`, the
first one being the reference), without any significance test: a small change
between two single runs means nothing.

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

A run holds credentials of its cluster in clear: see
[Security](../explanation/concepts.md#security) before sharing one.

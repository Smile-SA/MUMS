# Your first benchmark

From a fresh machine to a comparison between two optimizers: install the
platform, check it with a short run, then measure Kubernetes' default scheduler
and Koordinator, and compare them. Count about an hour, most of it waiting for
runs.

## 1. Prerequisites

A Linux machine (`amd64` or `arm64`) with:

- **Python 3.11** or later, with `venv`;
- **kubectl**;
- **git**;
- **Docker**, running: the scenarios used here create their cluster with kind, in
  Docker.
- **lxcfs**, running with `--enable-cfs`, for the 15-min scenarios (see "lxcfs on
  the host" in the [kind module](../../modules/environment/kind/README.md)).

Other tools are installed by the platform when needed.

## 2. Install the platform

From the repository's directory:

```bash
./benchmark_platform/bootstrap.sh
```

This creates a virtual environment in `.venv`, installs the platform in it, and
writes its settings. To use another virtual environment, to install into your
current Python environment instead, or to get the development tools: see
`./benchmark_platform/bootstrap.sh --help` and
[settings and installation](../reference/settings.md). Open **a new terminal**, then check:

```bash
benchmark-platform config      # where modules and utils are, the environment used
benchmark-platform doctor      # the machine, the platform, the state of every module
```

Nothing needs to be activated: the platform uses its own environment.

## 3. Check that everything works

The scenario `configs/smoke-test.yaml` runs the whole chain for one minute: a kind
cluster, Prometheus, the Online Boutique demo application, Locust traffic, and
Kubernetes' default scheduler. Install what it needs, then run it:

```bash
benchmark-platform deps install --scenario configs/smoke-test.yaml
benchmark-platform run configs/smoke-test.yaml
```

The first run downloads images and charts, and takes a few minutes. You should see:

```text
Run: /…/output/smoke-test-20261006T120330Z-seed42
[environment]     create     ✓
[observability]   start      ✓
[optimizer]       start      ✓
[stack]           deploy     ✓
[traffic]         start      ✓
[run]             wait       ✓
[provenance]      collect    ✓
[traffic]         stop       ✓
[observability]   stop       ✓
[environment]     destroy    ✓
[post-processing] run        ✓
Run completed: /…/output/smoke-test-20261006T120330Z-seed42
```

Look at what the run produced:

```bash
RUN=$(ls -td output/smoke-test-* | head -1)
ls $RUN/data                              # openmetrics, http-requests, run-window, essential-tables
head -3 $RUN/data/http-requests/000001.csv
ls $RUN/data/essential-tables             # the eight tables
```

The [run directory reference](../reference/run-directory.md) describes it all.

## 4. Measure two optimizers

Two scenarios run the same 15-minute experiment, with a different optimizer:
`no-optimization` (Kubernetes' default scheduler, the reference point) and `koordinator`.
Both end with an evaluation, `basic-evaluation`, which summarizes each run in a few
indicators.

```bash
benchmark-platform deps install --scenario configs/koordinator-online-boutique-15min.yaml
benchmark-platform run configs/baseline-online-boutique-15min.yaml
benchmark-platform run configs/koordinator-online-boutique-15min.yaml
```

Keep the machine idle while they run: anything else running on it skews the
measures.

## 5. Compare them

```bash
benchmark-platform compare output/baseline-online-boutique-15min-* output/koordinator-online-boutique-15min-*
```

The first run is the reference. For each indicator (requests, latencies, errors,
node usage, availability...), the report gives each run's value, its change against
the reference, and ✓ or ✗ when it is better or worse.

Two runs are not enough to conclude: two identical runs already differ by a few
percent. Run each scenario several times, and look at changes beyond that
variability.

## Next

- [Running benchmarks](../guides/running-benchmarks.md): write your own scenarios,
  repeat and compare runs.
- [The catalogue](../modules.md): the available modules.
- [Your first module](first-module.md): add your own.

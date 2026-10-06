# Concepts

The benchmark platform checks whether a Kubernetes optimizer (a scheduler, a
descheduler, an autoscaler...) works **in a real cluster**: a real application,
real traffic, real metrics, observed while the system runs. It compares tools as
an operator would deploy them, on operational measures: latency, errors, node
usage, disruptions.

It is a small core and a set of interchangeable modules. The core runs a
scenario; the modules do everything else.

## Vocabulary

**Scenario.** A YAML file describing one experiment: which module plays each role,
with which arguments, for how long, with which seed.
([reference](../reference/scenario.md))

**Run.** One execution of a scenario. Each run gets its own directory, holding
everything it produced. ([reference](../reference/run-directory.md))

**Module.** A directory with a descriptor (`module.yaml`) and the scripts that do
the work. Each module has a **type**, which fixes the actions it implements:

| Type | Role |
|---|---|
| `environment` | provides a Kubernetes cluster |
| `observability` | measures the cluster while the run lasts |
| `stack` | deploys the application under test |
| `optimizer` | the tool being evaluated |
| `traffic` | sends load to the application |
| `post-processing` | turns data into tables, indicators, comparisons |

A module is designated by its name. ([reference](../reference/module-contract.md),
[catalogue](../modules.md))

**Util.** A shared building block (a directory with a `util.yaml`): scripts that
modules, or the platform, call, such as installing Helm charts or starting a Kafka
broker. A util can also be a tool run by hand (`compare`).

**Standard data.** What modules exchange: files in a standard format, stored by
format in the run's data directory (`data/<format>/`). A module reads a format
without knowing who produced it. ([reference](../formats/README.md))

**Extras and logs.** Each module also has its own directories for its logs and for
anything else it keeps. They help understand a run; nothing evaluates a run from
them.

**Provenance.** What produced a run's results: the scenario, the platform's
version, a digest of each module and of each command they use, the machine, and a
snapshot of the cluster at the end of the run.
([reference](../reference/run-directory.md#provenance))

**Settings.** Where the modules and utils are, and the environment everything runs
in, set for each installation of the platform.
([reference](../reference/settings.md))

## A run, step by step

```text
[environment]     create     the cluster
[observability]   start      measurement starts
[optimizer]       start      the tool under test
[stack]           deploy     the application
[traffic]         start      the load starts
[run]             wait       the run's duration: the measured period
[provenance]      collect    the cluster as it was measured
[traffic]         stop       then everything stops, in reverse order
[stack]           delete
[optimizer]       stop
[observability]   stop
[environment]     destroy
[post-processing] run        each post-processing module, in the scenario's order
```

- **The order is fixed.** The optimizer starts before the application, as a
  scheduler is deployed: it is in place when the application's pods are created.
  The traffic starts last, right before the wait, so that the load starts with the
  measured period, the same for every optimizer, however long it takes to start.
- **The run window** is the wait, from its start to its end. It is written as
  standard data (`run-window`), so that evaluations can count only what happened
  during it.
- **Stops are always called**, in reverse order, for every module that was started,
  even if a later step failed. The environment is always destroyed, unless the
  scenario asks to keep it.
- **Post-processing runs last**, once the environment is gone: it only reads
  standard data. Each module may read what the previous ones wrote.
- **On failure**, the run stops at the step that failed, then stops and destroys
  what was started, and runs post-processing on what was collected. **On
  interruption** (Ctrl+C), the same, without post-processing.

## Known limitations

- **A test platform, not a production one.** It is not secured: never put real
  secrets in it. A run's provenance holds the cluster's Secrets in clear: check a
  run before sharing it.
- **Runs vary.** Two runs of the same scenario differ by a few percent, more on
  small values: conclude from repeated runs, not from one, on an otherwise idle
  machine.
- **Only pinned versions can be run again identically.** The provenance records
  what ran (module digests, commands, images), but a module that installs tools
  without fixing their version may run another version next time.

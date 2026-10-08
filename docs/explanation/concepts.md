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
| `disruption` | disrupts the cluster during the run (nodes, pods, network...) |
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

**Logs and extras.** Each module may also have its own directories: logs, for what
is a log; extras, for everything else that has no other place, notably what is
produced to explain or debug a run. Nothing evaluates a run from them.

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
[disruption]      start      the disruptions are set up
[traffic]         start      the load starts
[run]             wait       the run's duration: the measured period
[provenance]      collect    the cluster as it was measured
[traffic]         stop       then everything stops, in reverse order
[disruption]      stop
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
  Disruptions are set up just before it, and act in the background at times their
  module chooses.
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

## Principles

What the platform holds to. [Design](design.md) shows how they translate into
concrete choices.

### A cloud tool, for cloud people

The platform checks whether an optimizer works in a real cluster; it is not a test
bench comparing algorithms on instances. Tools are compared as an operator would
deploy them, with their default or documented configuration, on operational
measures: latency, errors, nodes (hence cost), disruptions, the tool's own
reliability. Easy configuration is part of a tool's quality: a module choosing good
defaults is not cheating. But a tool is never tuned on the scenario whose results
are published, and the configuration used for each tool is documented.

### Conditions as real as possible

A real cluster, a real application, real traffic, real metrics, observed while the
system runs. Whatever departs from real conditions must be justified. It remains a
realistic **test** platform, not a production one: see [Security](#security).

### As replayable as possible

A run is made as replayable as possible (a seed, pinned versions, a provenance of
what ran), accepting the nondeterminism of a realistic environment: two runs of the
same scenario differ. Runs are compared in the same conditions, and conclusions come
from repeated runs.

### The core and the modules ignore each other

The core knows module **types** and their contract, never a specific module: no
tool is named in its code. Modules know their contract, not the core's inner
workings (its directories, its scenario names), and ignore each other: they meet
only through the cluster and through standard data formats. A module may speak of a
module type, and of the utils it depends on, never of another module.

*Why*: any module can be replaced, and new ones written by anyone, without touching
the core or the other modules.

### Only observability and post-processing evaluate

A module produces **standard data**, in standard formats that any module may read,
and **extras**, its own, for understanding a run. Only observability and
post-processing measure, and they measure every optimizer the same way. Nothing
evaluates a run from what a module reports about itself.

*Why*: an optimizer could claim moves it never made, or not report changes it made.
What is observed in the cluster is the only common ground.

### Record raw state, without interpreting it

To stay independent of tools, the platform records the cluster's generic state (every
Kubernetes object, discovered through the API) and the raw output of standard
commands, rather than interpreting a tool's own format.

*Why*: interpreting a tool's format ties the core to that tool. The core's only
dependencies are Python, bash and `kubectl`, plus `git` for the platform's own
provenance, best effort.

### Dependencies are always explicit

A module may depend on anything, but its dependencies are **declared** and
**identifiable** (a fixed version, a commit): no implicit dependency on the state
of the machine.

### Side tasks never fail a run

Everything that is not the benchmark itself (provenance, state collection, debug
extras) is best effort: a failure is recorded, and the run goes on.

### Fail loudly

A failure never passes silently. If a step cannot work (a missing dependency, a
module that does not start), the run stops as early as possible, with a message
saying what to do. A run ending "normally" with a dead module is worse than a run
that fails.

### The module contract is frozen at publication

Once published, the contract between the platform and modules (actions, arguments,
outputs, descriptor) no longer changes: changing it would break everyone's modules.

## Security

The platform is a **test** platform: it is not secured, and a run holds what gives
access to its cluster.

- **Never put real secrets in it**, nor run it against a cluster or account that
  holds any.
- **A run contains credentials in clear**: the cluster's kubeconfig
  (`runtime/kubeconfig`). On a real cloud provider, that is full access to the
  cluster, sometimes to the account. The cluster's Secrets are not recorded: only
  their names and types (`provenance/kubernetes/secrets.txt`).
- **Use credentials dedicated to the experiments, and revoke them before sharing
  results.** Otherwise, remove `runtime/kubeconfig` from a run before sharing it.

## Known limitations

- **Runs vary.** Two runs of the same scenario differ by a few percent, more on
  small values: conclude from repeated runs, not from one, on an otherwise idle
  machine.
- **Only pinned versions can be run again identically.** The provenance records
  what ran (module digests, commands, images), but a module that installs tools
  without fixing their version may run another version next time.

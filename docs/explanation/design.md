# Design

The principles the platform follows, and the choices that follow from them, each
with its reason.

## Principles

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
realistic **test** platform, not a production one: it is not secured, and a run's
outputs may hold the cluster's Secrets in clear.

### Empirical, not deterministic

The aim is to compare in the same conditions, and to check that what ran is what is
claimed, not to replay a run exactly. Two runs of the same scenario differ: results
come from repeated runs. Traceability is added only where it helps compare or check.

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

## Choices

**Modules and utils are designated by name, never by path.** A scenario or a
dependency does not depend on where files are. Modules are searched in the
installation's module directories, utils only in its utils directory: a module
calls a util through `BENCHMARK_UTILS_PATH`, so a util elsewhere would be
unreachable.

**Settings belong to each installation.** Where modules and utils are, and the
environment everything runs in, are written in a configuration file inside the
installation's venv, with environment variables to override them. They are applied
in one place, at the start of every command; the core knows no directory of its
own. *Why*: the standard scheme of command-line tools (a file, overridden by a
variable); variables alone are fragile; settings point to one copy of the platform,
so two installed copies must not share them.

**The venv is used, never activated.** The `env` setting is sourced by the platform
for everything it runs; the command is linked into `~/.local/bin`. *Why*: the
terminal stays clean, and a dependency check sees exactly what the actions will see.

**A module's defaults live in its scripts.** The platform passes only the arguments
the scenario gives; the descriptor describes each default. *Why*: one source for
each value, the script that uses it.

**Unknown fields are warnings.** In a scenario or a descriptor, an unknown field is
ignored with a warning. *Why*: a field too many never blocks a run; a wrong or
missing value does.

**A module declares every command it needs**, except bash and POSIX utilities,
`kubectl` included. *Why*: a rule without exception can be checked automatically;
the contract gives modules a kubeconfig, not `kubectl`; and a dependency check sees
the same environment as the actions, so anything missing shows before a run.

**The traffic starts last, right before the wait.** *Why*: the load shape starts
with the measured period, the same for every optimizer, however long it takes to
start.

**Provenance is recorded twice.** What does not change (scenario, platform, module
and command digests, machine) at the start, so that it exists even if the run fails;
the cluster's state at the end of the wait, before anything stops, when it is still
in the measured state.

**Comparison is split in three.** The util `compare` knows only the `summary` format
and takes data directories; `benchmark-platform compare` takes run directories (the
platform knows their layout) and calls it; the post-processing module
`reference-comparison` compares a run with a reference within the run. *Why*: each
knows only what belongs to it.

**Modules are named after the tool they integrate**, with a qualifier only to tell
variants apart, and no type prefix. *Why*: the convention of ecosystems where names
live inside a host tool (Helm charts, Ansible roles); the type is already in the
descriptor.

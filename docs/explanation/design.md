# Design

How the platform's [principles](concepts.md#principles) translate into concrete
choices, each with its reason: a reminder of why things are the way they are.

**Modules and utils are designated by name, never by path.** A scenario or a
dependency does not depend on where files are. Modules are searched in the
installation's module directories, utils only in its utils directory: a module
calls a util through `MUMS_UTILS_PATH`, so a util elsewhere would be
unreachable.

**Settings belong to each installation.** Where modules and utils are, and the
environment everything runs in, are written in a configuration file inside the
installation's venv, with environment variables to override them. They are applied
in one place, at the start of every command; the core knows no directory of its
own. *Why*: the standard scheme of command-line tools (a file, overridden by a
variable); variables alone are fragile; settings point to one copy of the platform,
so two installed copies must not share them.

**The platform applies its own environment.** The `env` setting (by default, the
installation's venv) is sourced by the platform for everything it runs, whatever the
terminal; the command is linked into `~/.local/bin`, so nothing needs activating.
*Why*: the terminal stays clean, and a dependency check sees exactly what the
actions will see.

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

**The order of the steps.** The optimizer starts before the application: that is
how a scheduler is deployed, deciding where a pod goes when it is created; moving
pods already placed is an extra capability of some tools. The traffic starts last,
right before the wait: the load then starts with the measured period, the same for
every optimizer, however long it takes to start.

**Provenance is recorded at two moments.** What does not change (scenario, platform, module
and command digests, machine) at the start, so that it exists even if the run fails;
the cluster's state at the end of the wait, before anything stops, when it is still
in the measured state.

**Comparison: a util, a command, a module.** The util `compare` knows only the
`summary` format and takes data directories; `mums compare` takes run
directories (the platform knows their layout) and calls it; the module
`reference-comparison` compares a run with a reference, within the run. *Why*: each
knows only what belongs to it.

**Modules are named after the tool they integrate**, with a qualifier only to tell
variants apart, and no type prefix. *Why*: the convention of ecosystems where names
live inside a host tool (Helm charts, Ansible roles); the type is already in the
descriptor.

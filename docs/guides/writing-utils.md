# Writing utils

A util is a shared building block: scripts that several modules call, such as
installing a Helm chart or starting a Kafka broker. Using one from a module is
covered in [Writing modules](writing-modules.md#use-a-util).

## When to write a util

When several modules need the same thing, and it is not a role of a run (that is a
module's job). A util has no actions and no place in a scenario: it is only called,
by modules, by the platform, or by hand.

## Its directory

```text
utils/<name>/
├── util.yaml          descriptor (required)
├── README.md
├── <script>...        the scripts modules call
└── dependencies.sh    dependency script (optional)
```

Utils are searched only in the installation's utils directory (the `utils_path`
setting): a module calls them through `MUMS_UTILS_PATH`, so a util elsewhere
could not be reached.

## `util.yaml`

```yaml
name: kafka
dependencies:
  commands: [docker]
```

`name` (unique among modules and utils), and `dependencies`, exactly as a module's:
commands, other utils, a dependency script. See
[the contract](../reference/module-contract.md#utils).

## Its scripts

- Each script is called directly by path: `$MUMS_UTILS_PATH/<name>/<script>`,
  with the arguments it documents. Choose them freely, and keep them stable: modules
  depend on them.
- A util knows nothing of the modules that use it: it takes what it needs as
  arguments (a kubeconfig, a version, a name), never a module's path or setting.
- A script that starts something (a broker, a port-forward) has a matching script
  or action to stop it, which succeeds whatever is left.
- What it downloads or builds goes in its own directory (and in `.gitignore`).

A util can also be a tool run by hand, such as `compare`: then also give it a usage
message (`--help`).

## Its README

Following [the model](../reference/module-contract.md#readme), with a section
**Scripts** instead of **Actions**: each script, its arguments and what it does.

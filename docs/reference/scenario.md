# Scenario format

A scenario is a YAML file describing one experiment. `mums validate`
checks it, `mums run` runs it.

## Example

```yaml
version: 1

scenario:
  name: baseline-online-boutique-15min
  seed: 42
  duration_seconds: 900

environment:
  module: kind
  workers: {count: 2, cpu: "2", memory: "4Gi"}

observability:
  module: prometheus-live-scraper
  frequency_seconds: 15

stack:
  module: online-boutique-v0.10.1

optimizer:
  module: no-optimization

disruption:
  module: no-disruption

traffic:
  module: online-boutique-locust
  shape: day_profile

post-processing:
  - module: essential-tables
  - module: basic-evaluation

output:
  root_directory: output
  cleanup_environment: true
```

## Fields

### Root

| Field | Required | Content |
|---|---|---|
| `version` | yes | `1` |
| `scenario` | yes | the experiment: see below |
| `environment`, `observability`, `stack`, `optimizer`, `disruption`, `traffic` | yes | one module each: see [Module sections](#module-sections) |
| `post-processing` | no | a module section, or a list of them, run in that order |
| `output` | yes | where the run goes: see below |

### `scenario`

| Field | Required | Content |
|---|---|---|
| `name` | yes | the scenario's name, used to name its runs |
| `seed` | yes | positive integer, given to the modules that take one (`environment`, `stack`, `disruption`, `traffic`) |
| `duration_seconds` | yes | positive integer: the duration of the run's wait, i.e. of the measured period |
| `description` | no | free text |

### Module sections

Each section names a module and gives its arguments:

```yaml
traffic:
  module: online-boutique-locust   # the module's name (required)
  shape: day_profile               # its arguments, as declared in its module.yaml
```

- `module` must designate a module found in the installation's module directories,
  of the section's type (a `traffic` section takes a traffic module).
- The other fields are the module's arguments, checked against its descriptor
  (type, required arguments). An argument not given is left to the module, which
  applies its own default. Each module's README lists its arguments.
- `log_dir` and `extras_dir` are given by the platform, never by the scenario.

### `post-processing`

A list of module sections, run one after the other, in that order, once the
environment is gone. Each entry takes its own arguments; a module may appear more
than once, with different arguments.

```yaml
post-processing:
  - module: essential-tables
  - module: request-count
    errors_only: true
```

A single module may also be given as a section rather than a list.

### `output`

| Field | Required | Content |
|---|---|---|
| `root_directory` | yes | directory holding the runs, relative to where the platform is started, or absolute |
| `cleanup_environment` | no | `false` keeps the environment after the run (default: `true`); destroy it later with `mums env clean` |

## Validation

- **Errors** stop before anything is created: a missing required field, a value of
  the wrong type, an unknown module, a module of the wrong type, missing
  dependencies.
- **Unknown fields** (anywhere in the scenario, or not declared by a module) are
  ignored, with a warning.

## Names derived from the scenario

| Name | Form | Example |
|---|---|---|
| run directory | `<name>-<UTC time>-seed<seed>` | `smoke-test-20261006T120330Z-seed42` |
| environment id | `<name>-<seed>-<hash>`: lowercase letters, digits and `-`, 40 characters at most | `smoke-test-42-48a5b0` |

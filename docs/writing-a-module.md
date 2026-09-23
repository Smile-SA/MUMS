# Writing a module

A **module** is a self-contained directory that implements one family of
benchmark-platform components (environment, stack, traffic, observability,
optimizer, or dataset). The runner discovers and calls each module by reading
`module.yaml` and invoking its entrypoint (`run.sh` by convention).

Modules are **self-describing**: they declare their own arguments
(`args:`), dependencies, and supported lifecycle actions (`lifecycle:`). The
core does not assemble module-specific CLI flags and does not know what
fields a given module's YAML section contains.

---

## Directory layout

```
<family>/<module-name>/
├── module.yaml   # descriptor — required
├── run.sh        # entrypoint — declared via `entrypoint:` in module.yaml
└── …             # any helpers your implementation needs
```

Examples from the existing codebase:
- `envs/kind/` — Kind environment
- `stacks/online-boutique/` — Online Boutique stack
- `traffic/online-boutique/` — Locust traffic generator
- `observability/prometheus/` — Prometheus scraper
- `optimizers/baseline/` — no-op baseline optimizer
- `optimizers/koordinator/` — Koordinator scheduler optimizer
- `observability/analysis/` — OpenMetrics → CSV dataset generator (`type: dataset`)

---

## `module.yaml` reference

```yaml
name: <family>.<module-name>    # dotted label; used in the run manifest
type: <family>                  # one of: environment, stack, traffic,
                                 #   observability, optimizer, dataset
entrypoint: run.sh              # REQUIRED: relative path inside the module dir.
                                 # There is no default — a component module
                                 # that omits this key fails to load.

lifecycle:                      # REQUIRED: which actions this module supports.
  <action>: "<positional-args>"
                                 # The value documents the argument signature
                                 # only — the runner reads just the keys.
                                 # Mandatory actions for the family are called
                                 # unconditionally (e.g. traffic.start,
                                 # observability.start/stop). Actions the
                                 # runner treats as optional (e.g.
                                 # traffic.stop) are only called when declared
                                 # here — see ModuleSpec.supports() in
                                 # benchmark_platform/modules.py. A component
                                 # module with no `lifecycle:` map fails
                                 # loudly instead of being assumed to support
                                 # everything.

args:                            # optional: this module's own argument schema.
  <field>:
    required: false              # if true, the field must be present in the
                                  #   scenario config section, or config
                                  #   loading fails before anything runs.
    default: <value>              # documentation only — the module itself
                                  #   must apply this default; the core does
                                  #   not inject it.
    type: string|positive_int|bool|mapping  # enforced by
                                  #   benchmark_platform.schema.validate_section
                                  #   when the field is present.

dependencies:                   # not read by the runner, but mandatory at
                                 # runtime: enforced by check_module_deps.sh /
                                 # install_module_deps.sh for selected modules
  commands: [kubectl, helm]      # must exist on PATH
  utils: [utils/helm]            # recursively resolved by check_module_deps.sh /
                                  #   install_module_deps.sh
  modules: [observability/prometheus]  # recursively resolved, same as utils
  python: [requirements.txt]
```

The runner reads `name`, `type`, `entrypoint`, `lifecycle`, and `args`. The
`dependencies` block is documentation for humans and for
`scripts/check_module_deps.sh` / `scripts/install_module_deps.sh`.

**Exemption for `utils/*` modules:** helper modules under `utils/` are never
loaded through `load_module()` — the runner never invokes them directly.
Their `module.yaml` exists only for recursive dependency resolution, so the
`entrypoint:` and `lifecycle:` requirements above do not apply to them.

---

## `run.sh` conventions

### Invocation

The runner always invokes the entrypoint **from the repository root**:

```
./<family>/<module-name>/run.sh <action> [args…]
```

The script must therefore use `SCRIPT_DIR` to locate its own helpers:

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

ACTION="${1:?action required}"
shift

case "$ACTION" in
  start)   do_start  "$@" ;;
  stop)    do_stop   "$@" ;;
  *)       echo "ERROR: unknown action '$ACTION'" >&2; exit 1 ;;
esac
```

### Exit codes

| Return | Meaning |
|--------|---------|
| `0`    | Success |
| non-zero | Failure — the runner aborts the run (for setup actions) or records an error (for teardown actions) |

Teardown actions (`stop`, `destroy`) are called with `check=False`, so a
non-zero exit is recorded in the manifest but does **not** prevent other teardown
steps from running.

### Stdout and stderr

Lifecycle actions may write to stdout and stderr for informational messages, progress, warnings, and errors.

The runner does not interpret stdout or stderr as structured return values. Their contents may be displayed in verbose mode and/or recorded in the component logs.

Modules should therefore not rely on a particular stdout or stderr format for communication with the runner.

### Result passing

When a lifecycle action produces a value that must be consumed by the runner or by another component, the value must be passed using the mechanism defined by the module type's contract.

Result-passing mechanisms are part of the module type contract and must be declared or documented independently of stdout and stderr.


---

## Positional arguments vs. module-specific config

The runner passes only **framework-level positionals** to each action —
values that are cross-cutting by nature (kubeconfig path, seed, output
directory). See "Action signatures by family" below for the exact list per
family.

Anything specific to your module (a traffic shape, a scrape frequency, a
worker sizing) is **not** turned into a CLI flag by the runner. Instead, your
module's entire scenario-config section is delivered opaquely in the
`BENCHMARK_COMPONENT_CONFIG` environment variable, and your module is
responsible for reading it and applying its own defaults.

### The wire format is YAML-compatible

The scenario config and `module.yaml` are **YAML** — users never author
JSON. On the wire, `BENCHMARK_COMPONENT_CONFIG` carries the module's own
section serialized in **YAML flow style** (a strict subset of YAML 1.2, also
valid JSON), so it is parseable by `jq`, `yq`, and `yaml.safe_load()` alike —
verified: PyYAML parses exactly what the runner emits.

Module authors **never parse it directly** — use `cfg_get` from
`scripts/lib/component_config.sh` (below). That helper is the abstraction
boundary: swapping its `jq` backend for `yq` later would change one file,
not every module. `jq` is already a declared system prerequisite; `yq` is
not installed anywhere, so moving to block-style YAML on the wire would
**add** a dependency, contrary to the goal of reducing them.

### Reading arguments with `scripts/lib/component_config.sh`

Source the shared helper and use `cfg_get <jq-filter> [default]`:

```bash
source "$(dirname "${BASH_SOURCE[0]}")/../../scripts/lib/component_config.sh"

SHAPE="$(cfg_get '.shape' 'day_profile')"
CYCLE_MINUTES="$(cfg_get '.cycle_minutes' '60')"
```

`jq` is a required system dependency of the platform, so this helper is
always available.

```yaml
# scenario config
traffic:
  type: k6
  module: traffic/k6
  shape: day_profile
  cycle_minutes: 60
  target_rps: 200        # custom field — no runner change needed
```

```bash
TARGET_RPS="$(cfg_get '.target_rps' '100')"
```

---

## Environment variables

The runner injects these variables into every action:

| Variable | Value |
|----------|-------|
| `BENCHMARK_RUN_DIR` | Root of the current run output directory |
| `BENCHMARK_LOG_DIR` | `$BENCHMARK_RUN_DIR/logs/` |
| `BENCHMARK_PID_DIR` | `$BENCHMARK_RUN_DIR/runtime/pids/` |
| `BENCHMARK_TRAFFIC_DIR` | `$BENCHMARK_RUN_DIR/traffic/` |
| `BENCHMARK_METRICS_DIR` | `$BENCHMARK_RUN_DIR/metrics/` |
| `BENCHMARK_ARTIFACT_DIR` | `$BENCHMARK_RUN_DIR/artifacts/<module-name>/` — this module's own namespaced artifact directory |
| `BENCHMARK_COMPONENT_CONFIG` | This module's scenario-config section, serialized as flow-style YAML (valid JSON) — read it with `cfg_get` |

There are no other module-specific env vars (no `KIND_NODE_IMAGE`,
`PROMETHEUS_LOCAL_PORT`, etc.) — those values live in
`BENCHMARK_COMPONENT_CONFIG` and are read with `cfg_get`, same as any other
module-specific field.

---

## Action signatures by family

These are the exact positional arguments the runner passes for each action.
Your `run.sh` must accept them; anything beyond these positionals comes from
`BENCHMARK_COMPONENT_CONFIG`.

### environment

```bash
# stdout must print the kubeconfig file path (single line, stripped)
run.sh create <seed> <result_file>

# teardown (check=False)
run.sh destroy <seed>
```
For environment modules, the `create` action receives a `result_file`.
The module must write the path of the generated kubeconfig to `result_file`.

### stack

```bash
run.sh deploy <kubeconfig> <seed>
```

### observability

```bash
run.sh start <kubeconfig> <metrics_dir>

# teardown (check=False)
run.sh stop <kubeconfig>
```

### traffic

```bash
run.sh start <kubeconfig> <seed>

# teardown (check=False), only called if the module's lifecycle: declares `stop`
run.sh stop <kubeconfig>
```

### optimizer

Minimal contract: the optimizer deploys onto the cluster and stops there. It
dies with the cluster on `environment destroy`; the runner never polls its
status.

```bash
run.sh deploy <kubeconfig>

# OPTIONAL — only called if declared in lifecycle:
run.sh start <kubeconfig>

# OPTIONAL, teardown (check=False) — only called if declared in lifecycle:
run.sh stop <kubeconfig>
```

Implement `start`/`stop` only if your optimizer runs a host-side process for
the duration of the run (e.g. an online optimizer consuming live metrics and
emitting placement decisions — see `optimizers/hots/`). When declared, the
runner calls `start` right after `deploy` (before traffic begins) and `stop`
during teardown, after `traffic.stop` and before `observability.stop`, so the
optimizer stops acting on the cluster before the metrics source goes away.

### dataset

```bash
run.sh generate <metrics_om_file> <datasets_output_dir>
```

The dataset module owns the "nothing to generate" case: if the metrics file
is missing or empty, exit `0` without generating anything (do not fail the
run). It also owns writing `datasets/dataset-metadata.yaml` once generation
succeeds, via the metadata CLI:

```bash
python3 -m benchmark_platform.datasets.metadata "${BENCHMARK_RUN_DIR}"
```

---

## Registering the module in a scenario config

Point the relevant section to your module directory with the `module:` key:

```yaml
traffic:
  type: k6                          # arbitrary label for the manifest
  module: traffic/k6                # relative path to your module directory
  shape: day_profile
  cycle_minutes: 60
```

The `module:` key overrides the default. If omitted, the runner uses its
built-in default for that family.

---

## Worked example — k6 traffic module

This example adds a minimal k6 traffic module at `traffic/k6/`.

### Step 1 — Create the module directory

```
traffic/k6/
├── module.yaml
├── run.sh
└── script.js
```

### Step 2 — `module.yaml`

```yaml
name: traffic.k6
type: traffic
entrypoint: run.sh

lifecycle:
  start: "<kubeconfig> <seed>"
  stop:  "<kubeconfig>"

args:
  shape:         { required: false, default: day_profile, type: string }
  cycle_minutes: { required: false, default: 60, type: positive_int }

dependencies:
  commands: [k6, kubectl]
  utils: []
  python: []
```

### Step 3 — `run.sh`

```bash
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../../scripts/lib/component_config.sh"

ACTION="${1:?action required}"
shift

case "$ACTION" in
  start)
    KUBECONFIG="$1"
    SEED="$2"
    SHAPE="$(cfg_get '.shape' 'day_profile')"
    DURATION_MINUTES="$(cfg_get '.cycle_minutes' '60')"

    TARGET_URL="$(kubectl --kubeconfig="$KUBECONFIG" get svc frontend-external \
      -n default -o jsonpath='http://{.status.loadBalancer.ingress[0].ip}:80')"

    k6 run \
      --env SEED="$SEED" \
      --env SHAPE="$SHAPE" \
      --env DURATION_MINUTES="$DURATION_MINUTES" \
      --env TARGET_URL="$TARGET_URL" \
      --out csv="$BENCHMARK_TRAFFIC_DIR/k6-results.csv" \
      "$SCRIPT_DIR/script.js"
    ;;

  stop)
    # k6 exits when the test duration ends; nothing to stop
    ;;

  *)
    echo "ERROR: unknown action '$ACTION'" >&2
    exit 1
    ;;
esac
```

### Step 4 — Reference in a scenario config

```yaml
traffic:
  type: k6
  module: traffic/k6
  shape: day_profile
  cycle_minutes: 60
```

### Step 5 — Verify

```bash
make check   # shell syntax check picks up run.sh
benchmark-platform run configs/my-scenario.yaml
```

The runner will resolve `traffic/k6/module.yaml`, verify `type: traffic`, and
call `./traffic/k6/run.sh start <kubeconfig> <seed>` when the traffic phase
begins.

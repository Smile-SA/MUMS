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
├── run.sh        # entrypoint — required by convention
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
entrypoint: run.sh              # relative path inside the module dir.
                                 # Defaults to `run.sh` — declare this key only
                                 # when your entrypoint is named differently.

lifecycle:                      # authoritative: which actions this module supports.
  <action>: "run.sh <action> <positional-args>"
                                 # The runner calls mandatory actions for the
                                 # family unconditionally (e.g. traffic.start,
                                 # observability.start/stop). Actions the
                                 # runner treats as optional (e.g.
                                 # traffic.stop) are only called when declared
                                 # here — see ModuleSpec.supports() in
                                 # benchmark_platform/modules.py. A module with
                                 # no `lifecycle:` block at all is assumed to
                                 # support every action it's asked for
                                 # (back-compat default).

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

dependencies:                   # optional documentation — not enforced by the runner
  commands: [kubectl, helm]      # must exist on PATH
  utils: [utils/helm]            # recursively resolved by check_module_deps.sh /
                                  #   install_module_deps.sh
  modules: [observability/prometheus]  # recursively resolved, same as utils
  python: [requirements.txt]
```

The runner reads `name`, `type`, `entrypoint`, `lifecycle`, and `args`. The
`dependencies` block is documentation for humans and for
`scripts/check_module_deps.sh` / `scripts/install_module_deps.sh`.

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

| Action | stdout | stderr |
|--------|--------|--------|
| `environment create` | **Must print the kubeconfig file path** (single line) | goes to the terminal |
| all others | appended to a log file in `$BENCHMARK_LOG_DIR` | same log file |

For every action except `environment create`, stdout and stderr are both
redirected to a log file by the runner. You do not need to silence debug output.

---

## Positional arguments vs. module-specific config

The runner passes only **framework-level positionals** to each action —
values that are cross-cutting by nature (kubeconfig path, seed, output
directory). See "Action signatures by family" below for the exact list per
family.

Anything specific to your module (a traffic shape, a scrape frequency, a
worker sizing) is **not** turned into a CLI flag by the runner. Instead, your
module's entire scenario-config section is delivered as opaque JSON in the
`BENCHMARK_COMPONENT_CONFIG` environment variable, and your module is
responsible for reading it and applying its own defaults.

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
| `BENCHMARK_COMPONENT_CONFIG` | This module's scenario-config section, JSON-encoded |

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
run.sh create <seed>

# teardown (check=False)
run.sh destroy <seed>
```

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
status and never calls `stop`/`collect` on it. Only implement those as
additional lifecycle actions if your optimizer runs a host-side process that
needs explicit teardown — and declare them in `lifecycle:` if so.

```bash
run.sh deploy <kubeconfig>
```

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
  start: "run.sh start <kubeconfig> <seed>"
  stop:  "run.sh stop <kubeconfig>"

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

# Writing a module

A **module** is a self-contained directory that implements one family of
benchmark-platform components (environment, stack, traffic, observability,
optimizer, or dataset). The runner discovers and calls each module by reading
`module.yaml` and invoking `run.sh <action> [args…]`.

---

## Directory layout

```
<family>/<module-name>/
├── module.yaml   # descriptor — required
├── run.sh        # entrypoint — required
└── …             # any helpers your implementation needs
```

Examples from the existing codebase:
- `envs/kind/` — Kind environment
- `stacks/online-boutique/` — Online Boutique stack
- `traffic/online-boutique/` — Locust traffic generator
- `observability/prometheus/` — Prometheus scraper
- `optimizers/baseline/` — no-op baseline optimizer
- `observability/analysis/` — OpenMetrics → CSV dataset generator

---

## `module.yaml` reference

```yaml
name: <family>.<module-name>    # dotted label; used in the run manifest
type: <family>                  # one of: environment, stack, traffic,
                                #   observability, optimizer, dataset
entrypoint: run.sh              # relative path inside the module dir (default: run.sh)

lifecycle:                      # optional documentation — not parsed by the runner
  <action>: "run.sh <action> <positional-args>"

dependencies:                   # optional documentation — not enforced by the runner
  commands: [kubectl, helm]
  utils: [utils/helm]
  python: []
```

The runner only reads `name`, `type`, and `entrypoint`. The `lifecycle` and
`dependencies` blocks are documentation for humans.

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

## Environment variables

The runner injects these variables into every action:

| Variable | Value |
|----------|-------|
| `BENCHMARK_RUN_DIR` | Root of the current run output directory |
| `BENCHMARK_LOG_DIR` | `$BENCHMARK_RUN_DIR/logs/` |
| `BENCHMARK_PID_DIR` | `$BENCHMARK_RUN_DIR/pids/` |
| `BENCHMARK_TRAFFIC_DIR` | `$BENCHMARK_RUN_DIR/traffic/` |
| `BENCHMARK_METRICS_DIR` | `$BENCHMARK_RUN_DIR/metrics/` |
| `KIND_NODE_IMAGE` | Kind node image (from scenario config) |
| `METALLB_IP_RANGE` | MetalLB IP range (from scenario config) |
| `PROMETHEUS_LOCAL_PORT` | Prometheus local port (from scenario config) |
| `PROMETHEUS_SCRAPE_TIMEOUT` | Prometheus scrape timeout in seconds |
| `BENCHMARK_COMPONENT_CONFIG` | Full component section from the scenario config, JSON-encoded |

### Reading extra parameters via `BENCHMARK_COMPONENT_CONFIG`

Any key you add to a component's section in the scenario config is automatically
available to the module without changes to the runner.

```yaml
# scenario config
traffic:
  type: k6
  module: traffic/k6
  shape: day_profile
  cycle_minutes: 60
  target_rps: 200        # custom field
```

In `run.sh`, read it with `jq` (or any JSON parser):

```bash
TARGET_RPS=$(echo "$BENCHMARK_COMPONENT_CONFIG" | jq -r '.target_rps // 100')
```

Or with Python:

```bash
TARGET_RPS=$(python3 -c "import json,os; print(json.loads(os.environ['BENCHMARK_COMPONENT_CONFIG']).get('target_rps', 100))")
```

The standard positional arguments (kubeconfig, seed, --shape, etc.) are passed
regardless — `BENCHMARK_COMPONENT_CONFIG` is an addition, not a replacement.

---

## Action signatures by family

These are the exact arguments the runner passes for each action. Your `run.sh`
must accept them. The `module.yaml` lifecycle block is only documentation.

### environment

```bash
# stdout must print the kubeconfig file path (single line, stripped)
run.sh create <seed> --workers=count=N,cpu=X,memory=YGi

# teardown (check=False)
run.sh destroy <seed>
```

### stack

```bash
run.sh deploy <kubeconfig> <seed>
```

### observability

```bash
run.sh start <kubeconfig> <metrics_dir> --frequency=<seconds>

# teardown (check=False)
run.sh stop <kubeconfig>
```

### traffic

```bash
run.sh start <kubeconfig> <seed> --shape=<shape_name> --duration=<cycle_minutes>

# teardown (check=False)
run.sh stop <kubeconfig>
```

### optimizer

```bash
run.sh start
```

### dataset

```bash
run.sh generate <metrics_om_file> <datasets_output_dir>
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
  start: "run.sh start <kubeconfig> <seed> --shape=<shape> --duration=<cycle_minutes>"
  stop:  "run.sh stop <kubeconfig>"

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

ACTION="${1:?action required}"
shift

case "$ACTION" in
  start)
    KUBECONFIG="$1"
    SEED="$2"
    # parse --shape= and --duration= from remaining args
    SHAPE="day_profile"
    DURATION_MINUTES=60
    for arg in "${@:3}"; do
      case "$arg" in
        --shape=*)    SHAPE="${arg#--shape=}" ;;
        --duration=*) DURATION_MINUTES="${arg#--duration=}" ;;
      esac
    done

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
call `./traffic/k6/run.sh start …` when the traffic phase begins.

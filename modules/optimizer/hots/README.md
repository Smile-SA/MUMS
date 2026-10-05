# optimizers/hots

Wires HOTS (an online container-placement optimizer) and its `hots-connector`
bridge into a live benchmark run: the connector observes
the run's Prometheus and acts on the run's Kubernetes cluster, HOTS consumes
the connector's telemetry and emits placement decisions, both talk over a
per-run Kafka broker (`utils/kafka`) that this module starts and stops itself.

Unlike `optimizers/baseline`/`optimizers/koordinator`, this optimizer runs
host-side processes for the duration of the run: it declares `start`/`stop`
in `module.yaml`'s `lifecycle:`, so the runner starts it right after
`deploy` (a no-op here — nothing is installed into the cluster) and stops it
after traffic ends, before observability stops.

## Prerequisites

HOTS and hots-connector are separate repositories, not vendored into this
one. `dependencies.sh` installs them from local sibling checkouts:

```
../hots            # HOTS_REPO_PATH override
../hots-connector   # HOTS_CONNECTOR_REPO_PATH override
```

Run `make setup-module MODULE=optimizers/hots` (or `./scripts/install_module_deps.sh
optimizers/hots`) once both checkouts exist, or set `HOTS_REPO_PATH` /
`HOTS_CONNECTOR_REPO_PATH` if they live elsewhere. This installs both with
their `kafka` extras (`confluent-kafka`) and hots-connector's `kubernetes`
extra.

You also need a MILP solver on `PATH` for HOTS's placement problem (GLPK by
default: `glpsol`, from `libglpk-dev`/`glpk-utils`).

## Pinned choices

- **`k8s_workload_identity: pod`** — matches the platform's own refined
  dataset granularity (`datasets/pod_timeseries`, `datasets/pod_metadata`)
  and hots-connector's Prometheus `kubernetes` profile default
  (`workload_label=pod`). The `controller` identity mode exists in
  hots-connector but isn't wired here.
- **`k8s_node_label_key: kubernetes.io/hostname`** — Kind's (and most
  distributions') built-in node identity label; no extra labeling step
  needed on the cluster.
- **`prometheus_url` must match the `observability` module's
  `local_port`.** Modules don't read each other's scenario-config sections
  (see `docs/writing-a-module.md`), so this isn't derived automatically —
  if you change `observability.local_port` in your scenario config, update
  `optimizer.prometheus_url` to match.

## What `start` does

1. Starts a single-node, ephemeral Kafka broker for this run
   (`utils/kafka/broker.sh start`).
2. Renders a HOTS config JSON (`render_config.py`) into
   `BENCHMARK_ARTIFACT_DIR/hots-config.json`, including per-node CPU
   capacities queried live from the cluster.
3. Starts `hots-connector api` (Kubernetes action backend,
   `prometheus_kubernetes` observation backend), waits for `/health`, then
   calls `POST /stream/start`.
4. Starts `hots --config .../hots-config.json` (Kafka connector, runs until
   stopped).
5. Starts an independent Kafka consumer (`record_moves.py`) on the moves
   topic, appending each move to `BENCHMARK_ARTIFACT_DIR/moves.jsonl` — this
   is the only place a moves log exists for the live Kafka path, since
   neither HOTS nor hots-connector persists one when wired this way.

## What `stop` does

Calls hots-connector's `POST /kubernetes/reset-node-selectors` (best-effort;
undoes the `nodeSelector` patches made so far — only covers patches made
*this process*, lost across a crash/restart) and `POST /stream/stop`, then
SIGTERMs HOTS (its own shutdown handler flushes `hots-metrics.csv`), the
connector, and the moves recorder, and tears down the per-run Kafka broker.

## Artifacts

Everything lands under `artifacts/hots/`:
`hots-config.json`, `hots-metrics.csv`, `hots.log`, `moves.jsonl`.

## Offline dataset -> HOTS (no live cluster/Kafka)

`dataset_bridge.py` converts a completed run's refined dataset
(`datasets/pod_timeseries`, `datasets/pod_metadata`, `datasets/node_metadata`)
into HOTS's `FileConnector` input shape, for replaying a run through HOTS
without a live cluster:

```text
python3 optimizers/hots/dataset_bridge.py <run_dir> <output_dir>
```

See `docs/datasets.md`'s "Offline dataset -> HOTS" section for the column
mapping and rationale.

## Known limitations

- **Intermittent single-node Kafka broker startup flakiness.** In testing,
  `utils/kafka/broker.sh`'s single-node KRaft broker occasionally left HOTS's
  own consumer group unable to bootstrap even after telemetry was
  confirmed flowing on `hots_data` and `__consumer_offsets` existed —
  `hots.log` shows `RuntimeError: Kafka bootstrap failed: no telemetry
  received before bootstrap timeout`. This was consistently reproducible
  and fixed by explicitly pre-creating `__consumer_offsets` (see the
  comment in `utils/kafka/broker.sh`); a residual, less frequent version of
  it was still occasionally observed afterward, with no root cause
  isolated beyond "single-node KRaft combined-mode group-coordinator
  timing." If `start` reports healthy but `hots.log` shows this traceback,
  re-running `stop` then `start` was sufficient in testing. Not something
  hots-connector, HOTS, or this module's own code is doing wrong — it's the
  bundled Kafka broker's own coordinator startup.
- **HOTS's Kafka connector ends the run on a single slow tick, not just a
  dead producer.** `KafkaConnector.load_next()` does one `poll()` of
  `connector.parameters.poll_timeout` and treats an empty result as "data
  source exhausted" — there is no distinction between "the connector died"
  and "this one tick was slow." `render_config.py` sets `poll_timeout` to
  `tick_seconds * 3 + 5` to make a false-exhaustion trip rare in practice
  (observed surviving several minutes of continuous telemetry in testing),
  but a sufficiently slow Prometheus/Kubernetes API call can still end a
  long-duration run early with no error, just a clean-looking exit. If a
  scenario's `optimizer.tick_seconds` is very small, or `duration_seconds`
  is very large, watch for `hots-metrics.csv`/`hots.log` stopping
  mid-run — this is not a crash and won't be logged as one.
- **A cold cluster may need more than one traffic cycle before HOTS ever
  proposes a move.** Clustering/optimization only runs once
  `window_duration` ticks (3, by default) have accumulated, and a real move
  additionally requires an actual imbalance the `tol`/`tol_move` thresholds
  consider worth acting on.

# hots

Optimizer module: runs HOTS (an online container-placement
optimizer) against the live cluster, through its `hots-connector` bridge. The
connector reads the workload's usage from a Prometheus and acts on the cluster
(it moves a workload by setting a `nodeSelector`); HOTS consumes the connector's
telemetry and emits placement decisions. Both talk over a Kafka broker that the
module starts for the run and removes at the end. All of them run on the host,
for the duration of the run.

## Actions

- `start <kubeconfig>`:
  1. checks that the Prometheus at `prometheus_url` answers;
  2. starts a Kafka broker for this run (util `kafka`), on `kafka_port`, and
     creates its two topics (`hots_data`, `hots_moves`) with the util;
  3. writes HOTS's configuration (`render_config.py`), with the nodes' CPU
     capacities read from the cluster;
  4. starts `hots-connector` (observation: Prometheus; transport: Kafka; action:
     Kubernetes), waits until it answers, checks its backends, and starts its
     data stream;
  5. starts HOTS (a second attempt if Kafka is not ready in time);
  6. starts a recorder of HOTS's decisions (`record_moves.py`), and checks it
     stays up.
- `stop <kubeconfig>`: asks `hots-connector` to undo the `nodeSelector` patches it
  made (best effort), stops its stream, then stops HOTS (which writes its metrics
  file on the way out), the connector, the recorder, and removes the Kafka broker.
  Succeeds whatever is running (a `start` that failed half-way included).

## Arguments

| Argument | Default | Description |
|---|---|---|
| `kafka_port` | `9092` | Host port of the run's Kafka broker. |
| `connector_port` | `8189` | Host port of `hots-connector`'s control API. |
| `prometheus_url` | `http://127.0.0.1:9090` | Prometheus that `hots-connector` reads usage from, reachable from the host (e.g. through a port-forward). It must be set by hand to match wherever that Prometheus is. |
| `k8s_workload_identity` | `pod` | What `hots-connector` treats as a workload to place. |
| `k8s_node_label_key` | `kubernetes.io/hostname` | Node label used in the `nodeSelector` that moves a workload (built in on most clusters). |
| `namespace` | `online-boutique` | Namespace of the workloads HOTS optimizes. |
| `metric` | `cpu` | Usage metric HOTS optimizes on. |
| `nb_clusters` | `3` | Number of clusters in HOTS's clustering of workloads. |
| `tick_seconds` | `10` | Period of HOTS's loop and of the connector's data publishing. |

## Data produced

None in a standard format.

## Extras, logs

- `extras/…/hots-config.json`: the configuration HOTS ran with.
- `extras/…/hots-metrics.csv`: HOTS's own indicators (written at `stop`).
- `extras/…/moves.jsonl`: the placement decisions HOTS emitted, as recorded on
  Kafka (decisions, not the moves actually observed in the cluster).
- `extras/…/*.pid`: internal state.
- `logs/…/hots.log`, `logs/…/hots-connector.log`, `logs/…/hots-moves-recorder.log`.

## Dependencies

`hots`, `hots-connector`, `glpsol` (GLPK, HOTS's MILP solver), docker (for the
Kafka broker; its daemon must run), python3, kubectl, curl, sha1sum, and the util
`kafka`. As in the other Python-based modules, the dependency script installs
`requirements.txt` with the platform's interpreter, and GLPK with `apt-get` if
missing.

HOTS and `hots-connector` are pinned in `requirements.txt` once published. Until
then (lines commented out), install them in the platform's environment first, e.g.
from local checkouts while developing HOTS:

```bash
benchmark-platform exec -- python3 -m pip install \
    -e "../hots[kafka]" -e "../hots-connector[kafka,kubernetes,docker]"
```

Provenance records which ones ran (`provenance/python-packages.txt`: for a git
checkout, its commit).

## Files

`run.sh` (actions), `render_config.py` (HOTS's configuration),
`record_moves.py` (decisions recorder), `dataset_bridge.py` (offline tool, see
below), `tests/`, `dependencies.sh`, `requirements.txt`, `module.yaml`.

`dataset_bridge.py` converts a finished run's tables into HOTS's file-connector
input, to replay a run through HOTS without a cluster. It is not used during a
run, and still reads the former layout of the tables (to update).

## Known limitations

- **Not pinned yet**: HOTS and `hots-connector` are not published, so
  `requirements.txt` cannot pin them; the installed ones are recorded in
  provenance.
- **Runs on the host**: HOTS, `hots-connector` and the Kafka broker are not in the
  cluster, so their resource use is not measured by the evaluations, unlike an
  optimizer installed in the cluster.
- **Moving a workload moves all its replicas**: the `nodeSelector` is set on the
  Deployment, so all its pods are recreated (under new names). Undoing the patches
  at `stop` only covers those made by this connector process (lost after a crash).
- **Single-node Kafka broker, occasionally slow to start**: HOTS's consumer group
  may fail to bootstrap (`hots.log`: `Kafka bootstrap failed: no telemetry
  received before bootstrap timeout`), even with telemetry flowing. Explicitly
  creating `__consumer_offsets` in the broker fixed the frequent case; a rarer
  one remains (group-coordinator timing in single-node KRaft mode). `start`
  retries once; if it still happens, `stop` then `start` was enough in testing.
- **One slow tick ends HOTS's run, silently**: HOTS's Kafka connector polls once
  per tick (`poll_timeout`) and treats an empty poll as the end of the data, not
  as a slow tick. `render_config.py` sets `poll_timeout` to `tick_seconds * 3 + 5`,
  which makes it rare, but a slow Prometheus or Kubernetes API call can still end
  a long run early, with a clean-looking exit: watch `hots-metrics.csv` and
  `hots.log` stopping mid-run.
- **No move on a cold cluster at first**: clustering and optimization only start
  once `window_duration` ticks (3 by default) have accumulated, and a move also
  needs an imbalance above HOTS's thresholds (`tol`, `tol_move`).

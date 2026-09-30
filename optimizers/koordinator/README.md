# optimizers.koordinator

Optimizer module: installs [Koordinator](https://koordinator.sh) (QoS-based
scheduling and rescheduling for Kubernetes) in the cluster, with its manager,
scheduler, descheduler and node agents (`koordlet`).

## Actions

- `start <kubeconfig>`: fetches the Helm chart of version `chart_version` if not
  downloaded yet, then installs it (release `koordinator`; the chart creates its
  own namespace, `koordinator-system`) and waits for its components to be ready.
- No `stop`: Koordinator goes away with the environment.

## Arguments

| Argument | Default | Description |
|---|---|---|
| `chart_version` | `1.7.0` | Version of the Koordinator Helm chart to install, like a node image: fetched at `start` if not downloaded yet. |
| `manager_replicas` | `1` | Replicas of `koord-manager`. |
| `scheduler_replicas` | `1` | Replicas of `koord-scheduler`. |
| `descheduler_replicas` | `1` | Replicas of `koord-descheduler`. |

## Data produced

None.

## What it evaluates

The optimizer starts after the stack: the application's pods are already placed
by the default scheduler. `koord-scheduler` only places pods that ask for it
(`schedulerName: koord-scheduler`), which a stack's pods usually do not. In the
current step order, Koordinator therefore acts through its descheduler
(rescheduling), not through its scheduler.

## Dependencies

`utils.helm`. The chart is fetched at `start`, so the first run with a given
version needs network access.

## Files

`run.sh` (actions), `module.yaml`.

## Known limitations

- Koordinator reads node **Capacity**: the environment must report the real
  size of its nodes there. If Capacity is the host's rather than the node's (e.g.
  nodes limited only through kubelet reservations), its decisions are based on
  wrong node sizes.
- The descheduler's default settings may not evict anything during a short run.

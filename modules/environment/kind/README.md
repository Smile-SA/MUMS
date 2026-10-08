# kind

Environment module: a local Kubernetes cluster with [kind](https://kind.sigs.k8s.io)
(Kubernetes in Docker), plus MetalLB for `LoadBalancer` services.

## Actions

- `create <seed> <id> <output_file>`: creates the cluster, named after `<id>`
  (its Docker network too), and writes the path of its kubeconfig to
  `<output_file>`.
- `destroy <id>`: deletes the cluster `<id>` and its kubeconfig. Succeeds whatever
  is left: a complete, partial or absent cluster.

## Arguments

| Argument | Default | Description |
|---|---|---|
| `node_image` | `kindest/node:v1.34.0` | Kind node image (the Kubernetes version of the cluster). Kubernetes v1.35+ does not run on cgroup v1 hosts: the module refuses such an image there. |
| `workers` | one worker, without cpu or memory limit | `{count: N, cpu: X, memory: "YGi"}`: number of workers and the cpu/memory each one gets (cpu and memory optional). |
| `node_sizing` | `reserved` | How workers get the requested `cpu`/`memory` (see below). |

## `node_sizing`: how workers get their size

Kind nodes are containers on one host. The kubelet reads its node's size from
`/proc/meminfo` and sysfs, at start, never from cgroup limits, whatever the
cgroup version. Hence three modes, all working on cgroup v1 and v2 hosts:

| Mode | Capacity | Allocatable | CPU / memory enforced |
|---|---|---|---|
| `reserved` (default) | the host's | requested | memory yes (kubepods), CPU no (shares only) |
| `limits` | the host's | the host's | yes (Docker limits) |
| `lxcfs` | requested | requested (minus eviction threshold) | yes (Docker limits) |

- **`reserved`**: the kubelet reserves the rest of the host (`system-reserved`).
  The default scheduler uses Allocatable, so placement is right; tools that read
  Capacity see the host. Pods may use more CPU than requested when the host is idle.
- **`limits`**: `docker update --cpus/--memory` on the workers. The scheduler
  believes each node is the size of the host and overcommits it. Not for
  scheduling studies.
- **`lxcfs`**: Docker limits, plus [lxcfs](https://github.com/lxc/lxcfs) files
  mounted over the node's `/proc` files and `/sys/devices/system/cpu/online`, then
  the kubelets are restarted: each node looks like a VM of the requested size.
  Needs lxcfs running on the host (`/var/lib/lxcfs`), and whole CPUs.

## kind version

`kind-version` sets the kind binary:
- `system` (default): the system's `kind` (on PATH), whatever its version. If it
  is missing, the dependency script installs the latest release.
- a pinned version (`vX.Y.Z`): a module-local binary, `.bin/kind-vX.Y.Z`,
  installed by the dependency script, without touching the system's kind.

Kind releases build their own node images: recent kind versions usually run older
images, but not always. To keep a setup that breaks with newer kind, copy this
module, change its `name` in `module.yaml` (e.g. `kind-v0.32`: two modules
cannot share a name), and pin its `kind-version`.

## Extras

- `kubeconfig`: the kubeconfig of the cluster (its path is the one written to
  `<output_file>`).
- `kind-config.yaml`: the kind configuration the cluster was created with.

## Dependencies

Docker (installed by hand; its daemon is checked before each run), kind (see
above, installed by the module's `dependencies.sh`), kubectl, jq, curl (to
download kind), and the utils `helm` and `metallb`.

## Files

`kind.sh` (actions), `dependencies.sh`, `kind-version`, `module.yaml`; `.bin/`
(pinned kind binaries, not versioned).

## Known limitations

- Nodes are containers sharing the host's kernel: node-level metrics read from
  `/proc` (e.g. by a node exporter) describe the whole host, not the node.

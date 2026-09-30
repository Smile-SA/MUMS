# envs.kind

Environment module: a local Kubernetes cluster with [kind](https://kind.sigs.k8s.io)
(Kubernetes in Docker), plus MetalLB for `LoadBalancer` services.

## Arguments

| Argument | Default | Description |
|---|---|---|
| `node_image` | `kindest/node:v1.34.0` | Kind node image (the Kubernetes version of the cluster). Kubernetes v1.35+ does not run on cgroup v1 hosts: the module refuses such an image there. |
| `workers` | 1 worker, host resources | `{count: N, cpu: X, memory: "YGi"}`: number of workers and the cpu/memory each one gets. |
| `cgroups` | `v1` | How `cpu`/`memory` are enforced on the workers (see below). |

## `cgroups`: v1 or v2

- **`v1`** (default, works on any host): the kubelet reserves the rest of the host
  (`system-reserved`). Each worker's **Allocatable** is the requested cpu/memory,
  but its **Capacity stays the host's values**. Tools that read Capacity, such as
  some optimizers (e.g. Koordinator), then see wrong node sizes.
- **`v2`** (cgroup v2 hosts only): after creation, Docker limits
  (`docker update --cpus/--memory`) are applied to the worker containers. Each
  worker's **Capacity is the requested cpu/memory**. Use it for optimizers that
  read Capacity.

## kind version

`kind-version` sets the kind binary: `latest` (default) uses the `kind` on PATH
(installed from the latest release if missing); a pinned version (`vX.Y.Z`) uses a
module-local binary, `.bin/kind-vX.Y.Z`. Kind releases build their own node
images: recent kind versions usually run older images, but not always. To keep a
setup that breaks with newer kind, copy this module (e.g. `envs.kind-v0.32`) and
pin its `kind-version`.

## Dependencies

Docker (installed by hand; its daemon is checked before each run), kind (see
above, installed by the module's `dependencies.sh`), kubectl, jq, and the utils
`utils.helm` and `utils.metallb`.

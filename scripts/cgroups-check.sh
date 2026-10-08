#!/usr/bin/env bash
# Compares how the kind module sizes its worker nodes, mode by mode, on this host.
# For each mode: creates a cluster with the module itself, prints what Kubernetes
# sees (Capacity, Allocatable), what Docker enforces, what a node sees in /proc,
# and whether a pod too big for the requested node size still gets scheduled.
# Then destroys the cluster.
#
# Usage (from the repository root, module dependencies installed):
#   ./scripts/cgroups-check.sh [mode...]
# Modes: those of the module (cgroups: v1 v2, or node_sizing: reserved limits lxcfs);
# all of them by default (lxcfs only if lxcfs is running).
# Workers: 2 x {cpu: 2, memory: 4Gi} (override with WORKERS='{"count":..}').
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
MODULE="${ROOT}/modules/environment/kind"
export BENCHMARK_UTILS_PATH="${BENCHMARK_UTILS_PATH:-${ROOT}/utils}"
WORKERS="${WORKERS:-{\"count\":2,\"cpu\":\"2\",\"memory\":\"4Gi\"\}}"
WORK="$(mktemp -d)"

if grep -q '^  node_sizing:' "${MODULE}/module.yaml"; then
    ARG=node_sizing; ALL=(reserved limits)
    grep -qs " /var/lib/lxcfs fuse.lxcfs " /proc/mounts && ALL+=(lxcfs)
else
    ARG=cgroups; ALL=(v1 v2)
fi
MODES=("$@"); [ "${#MODES[@]}" -gt 0 ] || MODES=("${ALL[@]}")

echo "Host: $(nproc) CPUs, $(awk '/MemTotal/ {printf "%.1f GiB", $2/1048576}' /proc/meminfo)," \
     "cgroup fs: $(stat -fc %T /sys/fs/cgroup), docker $(docker version -f '{{.Server.Version}}' 2>/dev/null)," \
     "kind $(kind version 2>/dev/null | awk '{print $2}')"
echo "Workers requested: ${WORKERS}"

CURRENT=""
cleanup() { [ -n "$CURRENT" ] && "${MODULE}/kind.sh" destroy "$CURRENT" --extras_dir "${WORK}/${CURRENT}" >/dev/null 2>&1 || true; }
trap cleanup EXIT

for mode in "${MODES[@]}"; do
    id="cgcheck-${mode}"
    CURRENT="$id"
    echo
    echo "================ ${ARG}: ${mode} ================"
    if ! "${MODULE}/kind.sh" create 42 "$id" "${WORK}/${id}.out" --extras_dir "${WORK}/${id}" \
            --workers "$WORKERS" "--${ARG}" "$mode" > "${WORK}/${id}.log" 2>&1; then
        echo "create FAILED, log: ${WORK}/${id}.log"; tail -5 "${WORK}/${id}.log"; cleanup; CURRENT=""; continue
    fi
    kc="$(cat "${WORK}/${id}.out")"
    kubectl --kubeconfig "$kc" get nodes -o custom-columns=\
NODE:.metadata.name,CAP_CPU:.status.capacity.cpu,CAP_MEM:.status.capacity.memory,\
ALLOC_CPU:.status.allocatable.cpu,ALLOC_MEM:.status.allocatable.memory

    for node in $(docker ps --format '{{.Names}}' | grep -E "^${id}-worker[0-9]*$" | sort); do
        lim="$(docker inspect -f '{{.HostConfig.NanoCpus}} {{.HostConfig.Memory}}' "$node")"
        seen_cpu="$(docker exec "$node" grep -c ^processor /proc/cpuinfo)"
        seen_mem="$(docker exec "$node" awk '/MemTotal/ {printf "%.1fGiB", $2/1048576}' /proc/meminfo)"
        cg="$(docker exec "$node" sh -c 'cat /sys/fs/cgroup/cpu.max /sys/fs/cgroup/memory.max 2>/dev/null | tr "\n" " "' || true)"
        echo "${node}: docker limits [nanocpus memory]=[${lim}]; node sees ${seen_cpu} CPUs, ${seen_mem}; cgroup v2 cpu.max/memory.max: ${cg:-n/a}"
    done

    # A pod bigger than the requested node size (3 CPU, 5Gi on a 2 CPU / 4Gi worker):
    # it must stay Pending if the scheduler knows the real node size.
    target="$(docker ps --format '{{.Names}}' | grep -E "^${id}-worker$" | head -1)"
    kubectl --kubeconfig "$kc" apply -f - >/dev/null <<EOF
apiVersion: v1
kind: Pod
metadata: {name: too-big, namespace: default}
spec:
  nodeSelector: {kubernetes.io/hostname: ${target}}
  containers:
  - name: pause
    image: registry.k8s.io/pause:3.10
    resources: {requests: {cpu: "3", memory: 5Gi}}
EOF
    sleep 10
    scheduled="$(kubectl --kubeconfig "$kc" get pod too-big \
        -o jsonpath='{.status.conditions[?(@.type=="PodScheduled")].status}')"
    echo "Pod requesting 3 CPU / 5Gi on ${target}: PodScheduled=${scheduled:-?}" \
         "($( [ "$scheduled" = "True" ] && echo "node overcommitted" || echo "rejected, as on a real 2 CPU / 4Gi node"))"

    "${MODULE}/kind.sh" destroy "$id" --extras_dir "${WORK}/${id}" >/dev/null 2>&1 || true
    CURRENT=""
done
echo
echo "Logs: ${WORK}"

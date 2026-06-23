#!/usr/bin/env bash
set -euo pipefail

# Clean benchmark-created runtime environments.
#
# Usage:
#   ./scripts/clean_env.sh          # clean all kind-test-* environments
#   ./scripts/clean_env.sh 42       # clean kind-test-42 only
#
# This intentionally targets only benchmark-platform resources:
# - Kind clusters named kind-test-*
# - Docker networks named kind-test-*
# - kubeconfigs /tmp/kubeconfig-kind-test-*
# - benchmark PID files under output/runs/*/pids and /tmp

SEED="${1:-}"

kill_pid_file() {
    local pid_file="$1"

    [ -f "$pid_file" ] || return 0

    local pid
    pid="$(cat "$pid_file" 2>/dev/null || true)"

    if [[ "$pid" =~ ^[0-9]+$ ]]; then
        if kill -0 "$pid" 2>/dev/null; then
            echo "Stopping process from PID file: $pid_file (PID $pid)"
            kill "$pid" 2>/dev/null || true
            sleep 0.5
            kill -9 "$pid" 2>/dev/null || true
        else
            echo "Removing stale PID file: $pid_file"
        fi
    else
        echo "Removing invalid PID file: $pid_file"
    fi

    rm -f "$pid_file"
}

cleanup_pid_files() {
    echo "=== Cleaning benchmark PID files ==="

    find output/runs -path '*/pids/*.pid' -type f -print0 2>/dev/null \
        | while IFS= read -r -d '' pid_file; do
            kill_pid_file "$pid_file"
          done

    find /tmp -maxdepth 1 -type f \
        \( -name 'prometheus-pf-kubeconfig-kind-test-*.pid' \
        -o -name 'scraper-kubeconfig-kind-test-*.pid' \
        -o -name 'traffic-kubeconfig-kind-test-*.pid' \) \
        -print0 2>/dev/null \
        | while IFS= read -r -d '' pid_file; do
            kill_pid_file "$pid_file"
          done
}

delete_kind_cluster() {
    local cluster="$1"

    echo "=== Deleting Kind cluster: $cluster ==="
    kind delete cluster --name "$cluster" || true
}

remove_docker_network() {
    local network="$1"

    if ! docker network inspect "$network" >/dev/null 2>&1; then
        return 0
    fi

    echo "=== Removing Docker containers attached to network: $network ==="
    docker ps -aq --filter "network=$network" | xargs -r docker rm -f

    echo "=== Removing Docker network: $network ==="
    docker network rm "$network" >/dev/null 2>&1 || true
}

cleanup_kubeconfig() {
    local cluster="$1"
    local kubeconfig="/tmp/kubeconfig-${cluster}"

    if [ -f "$kubeconfig" ]; then
        echo "=== Removing kubeconfig: $kubeconfig ==="
        rm -f "$kubeconfig"
    fi
}

cleanup_cluster_name() {
    local cluster="$1"

    delete_kind_cluster "$cluster"
    remove_docker_network "$cluster"
    cleanup_kubeconfig "$cluster"
}

cleanup_pid_files

if [ -n "$SEED" ]; then
    cleanup_cluster_name "kind-test-${SEED}"
else
    echo "=== Cleaning all benchmark Kind clusters and Docker networks ==="

    mapfile -t kind_clusters < <(
        kind get clusters 2>/dev/null | grep '^kind-test-' || true
    )

    mapfile -t docker_networks < <(
        docker network ls --format '{{.Name}}' | grep '^kind-test-' || true
    )

    declare -A seen=()

    for cluster in "${kind_clusters[@]}"; do
        seen["$cluster"]=1
    done

    for network in "${docker_networks[@]}"; do
        seen["$network"]=1
    done

    for cluster in "${!seen[@]}"; do
        cleanup_cluster_name "$cluster"
    done

    rm -f /tmp/kubeconfig-kind-test-*
fi

echo "=== Benchmark environment cleanup complete ==="

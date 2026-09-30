#!/usr/bin/env bash
# Koordinator optimizer module (contract 1): installs Koordinator via Helm.
# It goes away with the environment: no stop action.
# The Helm chart of the requested version (--chart_version) is fetched at start
# if missing, like a node image.
#
# Usage:
#   run.sh start <kubeconfig> [--chart_version X.Y.Z] [--manager_replicas N]
#                [--scheduler_replicas N] [--descheduler_replicas N]

set -euo pipefail

UTILS_DIR="${BENCHMARK_UTILS_PATH:?BENCHMARK_UTILS_PATH is not set}"
CHART_REPO_URL="https://koordinator-sh.github.io/charts/"

usage() {
    echo "Usage: $0 start <kubeconfig> [--chart_version X.Y.Z] [--manager_replicas N] [--scheduler_replicas N] [--descheduler_replicas N]" >&2
    exit 1
}

ACTION="${1:-}"
if [ "$ACTION" != "start" ]; then
    [ -n "$ACTION" ] && echo "ERROR: unknown action '$ACTION'" >&2
    usage
fi
shift
[ "$#" -ge 1 ] || usage
KUBECONFIG_PATH="$1"
shift

CHART_VERSION=""
MANAGER_REPLICAS=1
SCHEDULER_REPLICAS=1
DESCHEDULER_REPLICAS=1

while [ "$#" -gt 0 ]; do
    case "$1" in
        --chart_version)        CHART_VERSION="$2";        shift 2 ;;
        --manager_replicas)     MANAGER_REPLICAS="$2";     shift 2 ;;
        --scheduler_replicas)   SCHEDULER_REPLICAS="$2";   shift 2 ;;
        --descheduler_replicas) DESCHEDULER_REPLICAS="$2"; shift 2 ;;
        *)
            echo "ERROR: unknown option '$1'" >&2
            usage
            ;;
    esac
done

if [ ! -f "$KUBECONFIG_PATH" ]; then
    echo "ERROR: kubeconfig '$KUBECONFIG_PATH' not found" >&2
    exit 1
fi

# No --namespace: the chart creates its own namespace (koordinator-system).
if [ -z "$CHART_VERSION" ]; then
    echo "ERROR: --chart_version is required" >&2
    exit 1
fi

# Like a node image: the requested chart version is fetched if missing.
"${UTILS_DIR}/helm/pull.sh" "$CHART_REPO_URL" koordinator "$CHART_VERSION"

"${UTILS_DIR}/helm/install.sh" \
    "$KUBECONFIG_PATH" \
    koordinator \
    koordinator \
    "$CHART_VERSION" \
    --set "manager.replicas=${MANAGER_REPLICAS}" \
    --set "scheduler.replicas=${SCHEDULER_REPLICAS}" \
    --set "descheduler.replicas=${DESCHEDULER_REPLICAS}"

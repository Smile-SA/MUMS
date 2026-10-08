#!/usr/bin/env bash
# Online Boutique stack module (contract 1): deploys the application via Helm.
#
# Usage:
#   run.sh deploy <kubeconfig> <seed>
#
# No `delete` action: the application goes away with the environment.
# The Helm chart is fetched at install time by dependencies.sh
# (`benchmark-platform deps install online-boutique-v0.10.1`).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
UTILS_DIR="${BENCHMARK_UTILS_PATH:?BENCHMARK_UTILS_PATH is not set}"

RELEASE_NAME="onlineboutique"
NAMESPACE="online-boutique"
POD_READY_TIMEOUT_SECONDS=300

usage() {
    echo "Usage: $0 deploy <kubeconfig> <seed>" >&2
    exit 1
}

ACTION="${1:-}"
[ "$ACTION" = "deploy" ] || { [ -n "$ACTION" ] && echo "ERROR: unknown action '$ACTION'" >&2; usage; }
shift
[ "$#" -ge 2 ] || usage
KUBECONFIG_PATH="$1"
SEED="$2"   # unused: the deployment is deterministic
shift 2

if [ "$#" -gt 0 ]; then
    echo "ERROR: unexpected argument(s): $*" >&2
    usage
fi

if [ ! -f "$KUBECONFIG_PATH" ]; then
    echo "ERROR: kubeconfig '$KUBECONFIG_PATH' not found" >&2
    exit 1
fi

CHART_VERSION="$(tr -d '[:space:]' < "${SCRIPT_DIR}/chart-version")"
"${UTILS_DIR}/helm/install.sh" \
    "$KUBECONFIG_PATH" \
    "$RELEASE_NAME" \
    onlineboutique \
    "$CHART_VERSION" \
    --namespace "$NAMESPACE" \
    --values "${SCRIPT_DIR}/values.yaml"

# The stack is operational once all its pods are Ready. Reaching the frontend
# from outside (external IP, HTTP) is the traffic module's concern.
echo "=== Waiting for Online Boutique pods to become ready (timeout: ${POD_READY_TIMEOUT_SECONDS}s) ==="
if ! kubectl --kubeconfig "$KUBECONFIG_PATH" -n "$NAMESPACE" wait \
    --for=condition=Ready pod --all --timeout="${POD_READY_TIMEOUT_SECONDS}s"; then
    echo "ERROR: not all Online Boutique pods became ready." >&2
    kubectl --kubeconfig "$KUBECONFIG_PATH" -n "$NAMESPACE" get pods -o wide >&2 || true
    kubectl --kubeconfig "$KUBECONFIG_PATH" -n "$NAMESPACE" get events --sort-by='.lastTimestamp' >&2 || true
    exit 1
fi
echo "=== Online Boutique ready ==="

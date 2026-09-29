#!/bin/bash
# Deploys Prometheus on a Kubernetes cluster via Helm.
# Usage: ./deploy.sh <kubeconfig>
set -e

UTILS_DIR="${BENCHMARK_UTILS_PATH:?BENCHMARK_UTILS_PATH is not set}"

KUBECONFIG=$1

if [ -z "$KUBECONFIG" ]; then
    echo "Usage: $0 <kubeconfig>" >&2
    exit 1
fi

if [ ! -f "$KUBECONFIG" ]; then
    echo "ERROR: kubeconfig '$KUBECONFIG' not found" >&2
    exit 1
fi

"$UTILS_DIR/helm/install.sh" \
    "$KUBECONFIG" \
    prometheus \
    prometheus \
    --namespace monitoring

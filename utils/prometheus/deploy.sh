#!/bin/bash
# Déploie Prometheus sur un cluster k8s via Helm.
# Usage: ./deploy.sh <kubeconfig>
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UTILS_DIR="$SCRIPT_DIR/.."

KUBECONFIG=$1

if [ -z "$KUBECONFIG" ]; then
    echo "Usage: $0 <kubeconfig>" >&2
    exit 1
fi

if [ ! -f "$KUBECONFIG" ]; then
    echo "ERREUR: kubeconfig '$KUBECONFIG' introuvable" >&2
    exit 1
fi

"$UTILS_DIR/helm/install.sh" \
    "$KUBECONFIG" \
    prometheus \
    prometheus \
    --namespace monitoring

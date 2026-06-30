#!/bin/bash
# Deploys Online Boutique on a Kubernetes cluster via Helm.
#
# Usage: ./deploy.sh <kubeconfig> <seed>
#
# Prerequisite: run prepare.sh first.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UTILS_DIR="$SCRIPT_DIR/../../utils"

KUBECONFIG=$1
SEED=$2

if [ -z "$KUBECONFIG" ] || [ -z "$SEED" ]; then
    echo "Usage: $0 <kubeconfig> <seed>" >&2
    exit 1
fi

if [ ! -f "$KUBECONFIG" ]; then
    echo "ERROR: kubeconfig '$KUBECONFIG' not found" >&2
    exit 1
fi

"$UTILS_DIR/helm/install.sh" \
    "$KUBECONFIG" \
    "onlineboutique-${SEED}" \
    onlineboutique \
    --namespace online-boutique \
    --values "$SCRIPT_DIR/values.yaml"

echo "=== Waiting for Online Boutique frontend to become ready ===" >&2
FRONTEND_URL="$("${SCRIPT_DIR}/check_frontend.sh" "${KUBECONFIG}")"
echo "=== Online Boutique frontend ready: ${FRONTEND_URL} ===" >&2

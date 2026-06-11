#!/bin/bash
# Déploie Online Boutique sur un cluster k8s via Helm.
#
# Usage: ./deploy.sh <kubeconfig> <seed>
#
# Prérequis : avoir lancé prepare.sh au préalable.

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
    echo "ERREUR: kubeconfig '$KUBECONFIG' introuvable" >&2
    exit 1
fi

"$UTILS_DIR/helm/install.sh" \
    "$KUBECONFIG" \
    "onlineboutique-${SEED}" \
    onlineboutique \
    --namespace online-boutique \
    --values "$SCRIPT_DIR/values.yaml"

echo "=== Validation de la disponibilité du frontend Online Boutique ===" >&2
FRONTEND_URL="$("${SCRIPT_DIR}/check_frontend.sh" "${KUBECONFIG}")"
echo "=== Frontend Online Boutique prêt: ${FRONTEND_URL} ===" >&2
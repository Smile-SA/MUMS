#!/bin/bash
# Déploie Koordinator sur un cluster k8s via Helm.
# Usage: ./deploy.sh <kubeconfig>
#
# TODO: passer les replicas en option
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UTILS_DIR="$SCRIPT_DIR/.."

MANAGER_REPLICAS=1
SCHEDULER_REPLICAS=1
DESCHEDULER_REPLICAS=1

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
    koordinator \
    koordinator \
    --namespace koordinator-system \
    --set manager.replicas=$MANAGER_REPLICAS \
    --set scheduler.replicas=$SCHEDULER_REPLICAS \
    --set descheduler.replicas=$DESCHEDULER_REPLICAS

#!/bin/bash
# Usage: ./install.sh <kubeconfig> <release_name> <chart> [helm options...]
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_REPOSITORY="$SCRIPT_DIR/chart-repository"

KUBECONFIG=$1
RELEASE_NAME=$2
CHART_NAME=$3
shift 3

if [ -z "$KUBECONFIG" ] || [ -z "$RELEASE_NAME" ] || [ -z "$CHART_NAME" ]; then
    echo "Usage: $0 <kubeconfig> <release_name> <chart> [helm options...]" >&2
    exit 1
fi

CHART_DIR="$CHART_REPOSITORY/$CHART_NAME"
if [ ! -d "$CHART_DIR" ]; then
    echo "ERREUR: chart '$CHART_NAME' introuvable dans $CHART_REPOSITORY — avez-vous lancé prepare.sh ?" >&2
    exit 1
fi

echo "=== Déploiement Helm: $RELEASE_NAME ===" >&2
echo "    Chart:     $CHART_DIR" >&2

helm install "$RELEASE_NAME" "$CHART_DIR" \
    --kubeconfig "$KUBECONFIG" \
    --create-namespace \
    --wait \
    "$@"

#!/bin/bash
# Usage: ./deploy.sh <kubeconfig> <release_name> <chart_name> [--namespace <ns>] [--values <file>]
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_REPOSITORY="$SCRIPT_DIR/chart-repository"

KUBECONFIG=$1
RELEASE_NAME=$2
CHART_NAME=$3
shift 3

NAMESPACE="default"
VALUES_FILE=""
while [[ "$#" -gt 0 ]]; do
    case $1 in
        --namespace) NAMESPACE="$2"; shift 2 ;;
        --values)    VALUES_FILE="$2"; shift 2 ;;
        *) shift ;;
    esac
done

if [ -z "$KUBECONFIG" ] || [ -z "$RELEASE_NAME" ] || [ -z "$CHART_NAME" ]; then
    echo "Usage: $0 <kubeconfig> <release_name> <chart_name> [--namespace <ns>] [--values <file>]" >&2
    exit 1
fi

CHART_DIR="$CHART_REPOSITORY/$CHART_NAME"
if [ ! -d "$CHART_DIR" ]; then
    echo "ERREUR: chart '$CHART_NAME' introuvable dans $CHART_REPOSITORY — avez-vous lancé prepare.sh ?" >&2
    exit 1
fi

echo "=== Déploiement Helm: $RELEASE_NAME ===" >&2
echo "    Chart:     $CHART_DIR" >&2
echo "    Namespace: $NAMESPACE" >&2
echo "    Values:    ${VALUES_FILE:-aucun}" >&2

if [ -n "$VALUES_FILE" ]; then
    helm install "$RELEASE_NAME" "$CHART_DIR" \
        --kubeconfig "$KUBECONFIG" \
        --namespace "$NAMESPACE" \
        --create-namespace \
        --wait \
        --values "$VALUES_FILE"
else
    helm install "$RELEASE_NAME" "$CHART_DIR" \
        --kubeconfig "$KUBECONFIG" \
        --namespace "$NAMESPACE" \
        --create-namespace \
        --wait
fi

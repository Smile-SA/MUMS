#!/bin/bash
# Usage: ./pull.sh <repo_name> <repo_url> <chart> <version>
#
# Si repo_name vaut "oci", le helm repo add est skippé
# et repo_url est utilisé directement comme source du chart.
# chart est alors ignoré.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_REPOSITORY="$SCRIPT_DIR/chart-repository"

REPO_NAME=$1
REPO_URL=$2
CHART=$3
VERSION=$4

if [ -z "$REPO_NAME" ] || [ -z "$REPO_URL" ] || [ -z "$CHART" ] || [ -z "$VERSION" ]; then
    echo "Usage: $0 <repo_name> <repo_url> <chart> <version>" >&2
    exit 1
fi

mkdir -p "$CHART_REPOSITORY"

if [[ "$REPO_NAME" == oci ]]; then
    # Mode OCI : REPO_URL est l'URL complète du chart, REPO_NAME et CHART ignorés
    echo "=== Téléchargement chart OCI: $REPO_URL version $VERSION ===" >&2
    helm pull "$REPO_URL" \
        --version "$VERSION" \
        --destination "$CHART_REPOSITORY" \
        --untar
else
    echo "=== Ajout repo Helm: $REPO_NAME ===" >&2
    helm repo add "$REPO_NAME" "$REPO_URL"
    helm repo update "$REPO_NAME"

    echo "=== Téléchargement chart: $CHART version $VERSION ===" >&2
    helm pull "$CHART" \
        --version "$VERSION" \
        --destination "$CHART_REPOSITORY" \
        --untar
fi

echo "=== Chart disponible dans $CHART_REPOSITORY ===" >&2

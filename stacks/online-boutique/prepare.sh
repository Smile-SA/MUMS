#!/bin/bash
# Télécharge le chart Helm d'Online Boutique depuis le repo GitHub.
# Usage: ./prepare.sh [version]
#
# Note: ce chart n'est pas disponible sur un repo Helm standard — il est
# récupéré directement depuis le repo GitHub GoogleCloudPlatform/microservices-demo,
# donc on n'utilise pas utils/helm/pull.sh.
#
# Le chart est dans helm-chart/ du repo GoogleCloudPlatform/microservices-demo.
# Le registre OCI officiel (us-docker.pkg.dev/online-boutique-ci) a été supprimé.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UTILS_DIR="$SCRIPT_DIR/../../utils"
CHART_REPOSITORY="$UTILS_DIR/helm/chart-repository"
CHART_DIR="$CHART_REPOSITORY/onlineboutique"

VERSION="${1:-v0.10.1}"
REPO_URL="https://github.com/GoogleCloudPlatform/microservices-demo.git"

if [ -d "$CHART_DIR" ]; then
    echo "=== Chart onlineboutique déjà présent, skip ===" >&2
    exit 0
fi

echo "=== Clonage microservices-demo tag $VERSION ===" >&2
TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

git clone --depth 1 --branch "$VERSION" "$REPO_URL" "$TMP_DIR"

mkdir -p "$CHART_REPOSITORY"
cp -r "$TMP_DIR/helm-chart" "$CHART_DIR"

echo "=== Chart disponible dans $CHART_DIR ===" >&2

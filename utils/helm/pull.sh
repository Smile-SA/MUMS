#!/bin/bash
# Fetches a Helm chart at a given version into chart-repository/<chart>/<version>/.
# Does nothing if that version is already there (safe to run again).
# Usage: ./pull.sh <repo_url> <chart> <version>
#   e.g. ./pull.sh https://prometheus-community.github.io/helm-charts prometheus 28.13.0
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_REPOSITORY="$SCRIPT_DIR/chart-repository"

REPO_URL="${1:-}"
CHART="${2:-}"
VERSION="${3:-}"

if [ -z "$REPO_URL" ] || [ -z "$CHART" ] || [ -z "$VERSION" ]; then
    echo "Usage: $0 <repo_url> <chart> <version>" >&2
    exit 1
fi

DEST="$CHART_REPOSITORY/$CHART/$VERSION"
if [ -d "$DEST" ]; then
    echo "=== Chart ${CHART} ${VERSION} already present ===" >&2
    exit 0
fi

echo "=== Pulling chart: ${CHART} ${VERSION} (${REPO_URL}) ===" >&2
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
# --repo: no `helm repo add`, so nothing is changed in the user's Helm configuration.
helm pull "$CHART" --repo "$REPO_URL" --version "$VERSION" --untar --untardir "$TMP"
mkdir -p "$CHART_REPOSITORY/$CHART"
mv "$TMP/$CHART" "$DEST"
echo "=== Chart available at $DEST ===" >&2

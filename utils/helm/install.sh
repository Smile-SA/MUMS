#!/bin/bash
# Installs a chart from chart-repository/<chart>/<version>/.
# Usage: ./install.sh <kubeconfig> <release_name> <chart> <version> [helm options...]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_REPOSITORY="$SCRIPT_DIR/chart-repository"

KUBECONFIG="${1:-}"
RELEASE_NAME="${2:-}"
CHART_NAME="${3:-}"
VERSION="${4:-}"
shift 4 || shift $#

if [ -z "$KUBECONFIG" ] || [ -z "$RELEASE_NAME" ] || [ -z "$CHART_NAME" ] || [ -z "$VERSION" ]; then
    echo "Usage: $0 <kubeconfig> <release_name> <chart> <version> [helm options...]" >&2
    exit 1
fi

CHART_DIR="$CHART_REPOSITORY/$CHART_NAME/$VERSION"
if [ ! -d "$CHART_DIR" ]; then
    echo "ERROR: chart '$CHART_NAME' version '$VERSION' not found in $CHART_REPOSITORY." >&2
    echo "  It is fetched by the module that uses it (see pull.sh)." >&2
    exit 1
fi

echo "=== Helm install: $RELEASE_NAME ($CHART_NAME $VERSION) ===" >&2
echo "    Chart:     $CHART_DIR" >&2

helm install "$RELEASE_NAME" "$CHART_DIR" \
    --kubeconfig "$KUBECONFIG" \
    --create-namespace \
    --wait \
    "$@"

#!/bin/bash
# Télécharge le chart Helm de Prometheus.
# Usage: ./prepare.sh <version>

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UTILS_DIR="$SCRIPT_DIR/.."

VERSION=$1

if [ -z "$VERSION" ]; then
    echo "Usage: $0 <version>" >&2
    exit 1
fi

"$UTILS_DIR/helm/pull.sh" \
    prometheus-community \
    https://prometheus-community.github.io/helm-charts \
    prometheus-community/prometheus \
    "$VERSION"

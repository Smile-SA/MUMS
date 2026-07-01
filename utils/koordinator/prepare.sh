#!/bin/bash
# Downloads the Koordinator Helm chart.
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
    koordinator-sh \
    https://koordinator-sh.github.io/charts/ \
    koordinator-sh/koordinator \
    "$VERSION"

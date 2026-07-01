#!/bin/bash
# Downloads the Online Boutique Helm chart from GitHub.
# Usage: ./prepare.sh [version]
#
# Note: this chart is not available on a standard Helm repository — it is
# fetched directly from the GoogleCloudPlatform/microservices-demo GitHub repo,
# so utils/helm/pull.sh is not used here.
#
# The chart lives in helm-chart/ of the GoogleCloudPlatform/microservices-demo repo.
# The official OCI registry (us-docker.pkg.dev/online-boutique-ci) was removed.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UTILS_DIR="$SCRIPT_DIR/../../utils"
CHART_REPOSITORY="$UTILS_DIR/helm/chart-repository"
CHART_DIR="$CHART_REPOSITORY/onlineboutique"

VERSION="${1:-v0.10.1}"
REPO_URL="https://github.com/GoogleCloudPlatform/microservices-demo.git"

if [ -d "$CHART_DIR" ]; then
    echo "=== Chart onlineboutique already present, skipping ===" >&2
    exit 0
fi

echo "=== Cloning microservices-demo tag $VERSION ===" >&2
TMP_DIR=$(mktemp -d)
trap "rm -rf $TMP_DIR" EXIT

git clone --depth 1 --branch "$VERSION" "$REPO_URL" "$TMP_DIR"

mkdir -p "$CHART_REPOSITORY"
cp -r "$TMP_DIR/helm-chart" "$CHART_DIR"

echo "=== Chart available at $CHART_DIR ===" >&2

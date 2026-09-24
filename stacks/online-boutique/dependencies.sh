#!/usr/bin/env bash
# Installs the Online Boutique Helm chart (run by `make setup-module`).
# Usage: ./dependencies.sh [version]
#
# Note: this chart is not available on a standard Helm repository — it is
# fetched directly from the GoogleCloudPlatform/microservices-demo GitHub repo,
# so utils/helm/pull.sh is not used here.
#
# The chart lives in helm-chart/ of the GoogleCloudPlatform/microservices-demo repo.
# The official OCI registry (us-docker.pkg.dev/online-boutique-ci) was removed.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
UTILS_DIR="$(cd "${SCRIPT_DIR}/../../utils" && pwd -P)"
CHART_REPOSITORY="$UTILS_DIR/helm/chart-repository"
CHART_DIR="$CHART_REPOSITORY/onlineboutique"

if [ -d "$CHART_DIR" ]; then
    echo "=== Chart onlineboutique already present, skipping ===" >&2
    exit 0
fi

# git is needed to fetch the chart: install it first if missing.
if ! command -v git >/dev/null 2>&1; then
    if command -v apt-get >/dev/null 2>&1; then
        echo "=== Installing git ===" >&2
        sudo apt-get update
        sudo apt-get install -y git
    else
        echo "ERROR: git is required to fetch the Online Boutique chart, and apt-get is" >&2
        echo "       not available to install it. Install git, then run this again." >&2
        exit 1
    fi
fi

VERSION="${1:-v0.10.1}"
REPO_URL="https://github.com/GoogleCloudPlatform/microservices-demo.git"

echo "=== Cloning microservices-demo tag $VERSION ===" >&2
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

git clone --depth 1 --branch "$VERSION" "$REPO_URL" "$TMP_DIR"

mkdir -p "$CHART_REPOSITORY"
cp -r "$TMP_DIR/helm-chart" "$CHART_DIR"

echo "=== Chart available at $CHART_DIR ===" >&2

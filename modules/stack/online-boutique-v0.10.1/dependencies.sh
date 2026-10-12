#!/usr/bin/env bash
# Online Boutique Helm chart, fetched from the GoogleCloudPlatform/microservices-demo
# GitHub repository (not published on a standard Helm repository, and the
# official OCI registry was removed), into
# utils/helm/chart-repository/onlineboutique/<version>/ (version in ./chart-version).
# Usage: ./dependencies.sh install|check
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
VERSION="$(tr -d '[:space:]' < "${SCRIPT_DIR}/chart-version")"   # git tag of microservices-demo
REPO_URL="https://github.com/GoogleCloudPlatform/microservices-demo.git"
CHART_REPOSITORY="${MUMS_UTILS_PATH:?}/helm/chart-repository"
CHART_DIR="$CHART_REPOSITORY/onlineboutique/$VERSION"

install() {
    if [ -d "$CHART_DIR" ]; then
        echo "=== Chart onlineboutique ${VERSION} already present, skipping ==="
        return 0
    fi
    # git is needed to fetch the chart: install it first if missing.
    if ! command -v git >/dev/null 2>&1; then
        if command -v apt-get >/dev/null 2>&1; then
            echo "=== Installing git ==="
            sudo apt-get update
            sudo apt-get install -y git
        else
            echo "ERROR: git is required and apt-get is not available: install git." >&2
            exit 1
        fi
    fi
    echo "=== Cloning microservices-demo tag $VERSION ==="
    local tmp; tmp="$(mktemp -d)"
    trap 'rm -rf "$tmp"' RETURN
    git clone --depth 1 --branch "$VERSION" "$REPO_URL" "$tmp"
    mkdir -p "$CHART_REPOSITORY/onlineboutique"
    cp -r "$tmp/helm-chart" "$CHART_DIR"
    echo "=== Chart available at $CHART_DIR ==="
}

case "${1:-}" in
    install) install ;;
    check) [ -d "$CHART_DIR" ] || { echo "Chart onlineboutique ${VERSION} not downloaded ($CHART_DIR)"; exit 1; } ;;
    *) echo "Usage: $0 install|check" >&2; exit 2 ;;
esac

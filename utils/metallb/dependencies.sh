#!/usr/bin/env bash
# MetalLB Helm chart, fetched into utils/helm/chart-repository/.
# Usage: ./dependencies.sh install|check
set -euo pipefail

VERSION="0.15.3"
CHART_DIR="${BENCHMARK_UTILS_PATH:?}/helm/chart-repository/metallb"

case "${1:-}" in
    install)
        if [ -d "$CHART_DIR" ]; then
            echo "=== Chart metallb already present, skipping ==="
            exit 0
        fi
        "${BENCHMARK_UTILS_PATH}/helm/pull.sh" \
            metallb \
            https://metallb.github.io/metallb \
            metallb/metallb \
            "$VERSION"
        ;;
    check)
        [ -d "$CHART_DIR" ] || { echo "Chart metallb not downloaded ($CHART_DIR)"; exit 1; }
        ;;
    *) echo "Usage: $0 install|check" >&2; exit 2 ;;
esac

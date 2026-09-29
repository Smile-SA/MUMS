#!/usr/bin/env bash
# Koordinator Helm chart, fetched into utils/helm/chart-repository/.
# The version is pinned so that every installation runs the same Koordinator.
# Usage: ./dependencies.sh install|check
set -euo pipefail

VERSION="1.7.0"
CHART_DIR="${BENCHMARK_UTILS_PATH:?}/helm/chart-repository/koordinator"

case "${1:-}" in
    install)
        if [ -d "$CHART_DIR" ]; then
            echo "=== Chart koordinator already present, skipping ==="
            exit 0
        fi
        "${BENCHMARK_UTILS_PATH}/helm/pull.sh" \
            koordinator-sh \
            https://koordinator-sh.github.io/charts/ \
            koordinator-sh/koordinator \
            "$VERSION"
        ;;
    check) [ -d "$CHART_DIR" ] || { echo "Chart koordinator not downloaded ($CHART_DIR)"; exit 1; } ;;
    *) echo "Usage: $0 install|check" >&2; exit 2 ;;
esac

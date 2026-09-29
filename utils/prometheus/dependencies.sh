#!/usr/bin/env bash
# Prometheus Helm chart, fetched into utils/helm/chart-repository/.
# Usage: ./dependencies.sh install|check
set -euo pipefail

VERSION="28.13.0"
CHART_DIR="${BENCHMARK_UTILS_PATH:?}/helm/chart-repository/prometheus"

case "${1:-}" in
    install)
        if [ -d "$CHART_DIR" ]; then
            echo "=== Chart prometheus already present, skipping ==="
            exit 0
        fi
        "${BENCHMARK_UTILS_PATH}/helm/pull.sh" \
            prometheus-community \
            https://prometheus-community.github.io/helm-charts \
            prometheus-community/prometheus \
            "$VERSION"
        ;;
    check)
        [ -d "$CHART_DIR" ] || { echo "Chart prometheus not downloaded ($CHART_DIR)"; exit 1; }
        ;;
    *) echo "Usage: $0 install|check" >&2; exit 2 ;;
esac

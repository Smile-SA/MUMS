#!/usr/bin/env bash
# Dependencies of the Prometheus observability module:
# - the scraper's Python packages (requirements.txt), installed with the
#   platform's interpreter (first on PATH);
# - the Prometheus Helm chart, fetched into utils/helm/chart-repository/.
# Usage: ./dependencies.sh install|check
set -euo pipefail

CHART_VERSION="28.13.0"
CHART_DIR="${BENCHMARK_UTILS_PATH:?}/helm/chart-repository/prometheus"

install() {
    python3 -m pip install -r requirements.txt
    if [ -d "$CHART_DIR" ]; then
        echo "=== Chart prometheus already present, skipping ==="
    else
        "${BENCHMARK_UTILS_PATH}/helm/pull.sh" \
            prometheus-community \
            https://prometheus-community.github.io/helm-charts \
            prometheus-community/prometheus \
            "$CHART_VERSION"
    fi
}

check() {
    python3 -c "import requests"
    [ -d "$CHART_DIR" ] || { echo "Chart prometheus not downloaded ($CHART_DIR)"; exit 1; }
}

case "${1:-}" in
    install) install ;;
    check) check ;;
    *) echo "Usage: $0 install|check" >&2; exit 2 ;;
esac

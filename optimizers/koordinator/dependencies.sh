#!/usr/bin/env bash
# Koordinator Helm chart (version in ./chart-version), fetched into
# utils/helm/chart-repository/koordinator/<version>/.
# Usage: ./dependencies.sh install|check
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
VERSION="$(tr -d '[:space:]' < "${SCRIPT_DIR}/chart-version")"
CHART_DIR="${BENCHMARK_UTILS_PATH:?}/helm/chart-repository/koordinator/${VERSION}"

case "${1:-}" in
    install) "${BENCHMARK_UTILS_PATH}/helm/pull.sh" https://koordinator-sh.github.io/charts/ koordinator "$VERSION" ;;
    check) [ -d "$CHART_DIR" ] || { echo "Chart koordinator ${VERSION} not downloaded ($CHART_DIR)"; exit 1; } ;;
    *) echo "Usage: $0 install|check" >&2; exit 2 ;;
esac

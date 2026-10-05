#!/usr/bin/env bash
# MetalLB Helm chart (version in ./chart-version), fetched into
# utils/helm/chart-repository/metallb/<version>/.
# Usage: ./dependencies.sh install|check
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
VERSION="$(tr -d '[:space:]' < "${SCRIPT_DIR}/chart-version")"
CHART_DIR="${BENCHMARK_UTILS_PATH:?}/helm/chart-repository/metallb/${VERSION}"

case "${1:-}" in
    install) "${BENCHMARK_UTILS_PATH}/helm/pull.sh" https://metallb.github.io/metallb metallb "$VERSION" ;;
    check) [ -d "$CHART_DIR" ] || { echo "Chart metallb ${VERSION} not downloaded ($CHART_DIR)"; exit 1; } ;;
    *) echo "Usage: $0 install|check" >&2; exit 2 ;;
esac

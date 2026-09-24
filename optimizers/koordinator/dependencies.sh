#!/usr/bin/env bash
# Installs the Koordinator Helm chart (run by `make setup-module`).
# Usage: ./dependencies.sh [version]
#   version: chart version (default: pinned below, so that every installation
#   runs the same Koordinator; change it deliberately).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
UTILS_DIR="$(cd "${SCRIPT_DIR}/../../utils" && pwd -P)"

VERSION="${1:-1.7.0}"

"${UTILS_DIR}/helm/pull.sh" \
    koordinator-sh \
    https://koordinator-sh.github.io/charts/ \
    koordinator-sh/koordinator \
    "$VERSION"

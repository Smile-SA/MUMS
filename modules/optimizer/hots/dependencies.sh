#!/usr/bin/env bash
# HOTS and hots-connector. UNDER REPAIR (see CHANTIERS.md): still installed from
# local sibling checkouts in editable mode; GLPK not handled yet.
# Usage: ./dependencies.sh install|check
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
PLATFORM_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd -P)"
HOTS_REPO_PATH="${HOTS_REPO_PATH:-${PLATFORM_ROOT}/../hots}"
HOTS_CONNECTOR_REPO_PATH="${HOTS_CONNECTOR_REPO_PATH:-${PLATFORM_ROOT}/../hots-connector}"

install() {
    for repo in "$HOTS_REPO_PATH" "$HOTS_CONNECTOR_REPO_PATH"; do
        if [ ! -d "$repo" ]; then
            echo "ERROR: checkout not found: $repo" >&2
            echo "  Clone it there, or export HOTS_REPO_PATH / HOTS_CONNECTOR_REPO_PATH." >&2
            exit 1
        fi
    done
    echo "=== Installing HOTS from ${HOTS_REPO_PATH} ==="
    python3 -m pip install -e "${HOTS_REPO_PATH}[kafka]"
    echo "=== Installing hots-connector from ${HOTS_CONNECTOR_REPO_PATH} ==="
    python3 -m pip install -e "${HOTS_CONNECTOR_REPO_PATH}[kafka,kubernetes,docker]"
}

case "${1:-}" in
    install) install ;;
    check)
        # hots / hots-connector / docker commands are checked by the core.
        docker info >/dev/null 2>&1 || { echo "Docker daemon not reachable (needed for the Kafka broker)"; exit 1; }
        python3 -c "import confluent_kafka"
        ;;
    *) echo "Usage: $0 install|check" >&2; exit 2 ;;
esac

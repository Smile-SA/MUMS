#!/usr/bin/env bash
# Python packages of the module (requirements.txt), installed with the platform's
# interpreter (first on PATH), as in the other Python-based modules; GLPK, the
# MILP solver HOTS uses (glpsol), installed with apt-get if missing.
#
# HOTS and hots-connector themselves: pinned in requirements.txt once published.
# Until then (lines commented out), they must already be installed in the
# platform's environment, e.g. from local checkouts while developing HOTS:
#   benchmark-platform exec -- python3 -m pip install -e "<hots>[kafka]" \
#       -e "<hots-connector>[kafka,kubernetes,docker]"
# Usage: ./dependencies.sh install|check
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

install() {
    python3 -m pip install -r "${SCRIPT_DIR}/requirements.txt"
    for command in hots hots-connector; do
        if ! command -v "$command" >/dev/null 2>&1; then
            echo "ERROR: ${command} is not installed, and not pinned in requirements.txt." >&2
            echo "  Pin it there, or install a checkout:" >&2
            echo "  benchmark-platform exec -- python3 -m pip install -e \"<checkout>[...]\"" >&2
            exit 1
        fi
    done
    if ! command -v glpsol >/dev/null 2>&1; then
        if command -v apt-get >/dev/null 2>&1; then
            echo "=== Installing GLPK (glpsol) ==="
            sudo apt-get update
            sudo apt-get install -y glpk-utils
        else
            echo "ERROR: GLPK (glpsol) is required and apt-get is not available: install GLPK." >&2
            exit 1
        fi
    fi
}

case "${1:-}" in
    install) install ;;
    check)
        # hots, hots-connector, glpsol and docker themselves are checked by the core.
        docker info >/dev/null 2>&1 || { echo "Docker daemon not reachable (needed for the Kafka broker)"; exit 1; }
        python3 -c "import confluent_kafka"
        ;;
    *) echo "Usage: $0 install|check" >&2; exit 2 ;;
esac

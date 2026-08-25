#!/usr/bin/env bash
# Installs HOTS and hots-connector from local sibling checkouts (they are
# separate repos, not vendored here -- see README.md).
#
# Override HOTS_REPO_PATH / HOTS_CONNECTOR_REPO_PATH if your checkouts don't
# live next to this repo's parent directory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd -P)"

HOTS_REPO_PATH="${HOTS_REPO_PATH:-${REPO_ROOT}/../hots}"
HOTS_CONNECTOR_REPO_PATH="${HOTS_CONNECTOR_REPO_PATH:-${REPO_ROOT}/../hots-connector}"

PYTHON_BIN="${PYTHON_BIN:-}"
if [ -z "${PYTHON_BIN}" ]; then
    if [ -x "${REPO_ROOT}/.venv/bin/python" ]; then
        PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
    else
        PYTHON_BIN="$(command -v python3 || true)"
    fi
fi

if [ -z "${PYTHON_BIN}" ]; then
    echo "[ERROR] No Python interpreter found." >&2
    exit 1
fi

if [ ! -d "${HOTS_REPO_PATH}" ]; then
    echo "[ERROR] HOTS repo not found at '${HOTS_REPO_PATH}'." >&2
    echo "  Tried: ${HOTS_REPO_PATH}" >&2
    echo "  Fix option A: clone/symlink hots next to this repo as 'hots'" >&2
    echo "  Fix option B: export HOTS_REPO_PATH=/absolute/path/to/your/hots/checkout" >&2
    exit 1
fi
if [ ! -d "${HOTS_CONNECTOR_REPO_PATH}" ]; then
    echo "[ERROR] hots-connector repo not found at '${HOTS_CONNECTOR_REPO_PATH}'." >&2
    echo "  Tried: ${HOTS_CONNECTOR_REPO_PATH}" >&2
    echo "  Fix option A: clone/symlink hots-connector next to this repo as 'hots-connector'" >&2
    echo "  Fix option B: export HOTS_CONNECTOR_REPO_PATH=/absolute/path/to/your/hots-connector/checkout" >&2
    exit 1
fi

echo "=== Installing HOTS from ${HOTS_REPO_PATH} ===" >&2
"${PYTHON_BIN}" -m pip install -e "${HOTS_REPO_PATH}[kafka]"

echo "=== Installing hots-connector from ${HOTS_CONNECTOR_REPO_PATH} ===" >&2
"${PYTHON_BIN}" -m pip install -e "${HOTS_CONNECTOR_REPO_PATH}[kafka,kubernetes,docker]"

#!/usr/bin/env bash
# Installs the benchmark platform (its core): creates a Python virtual
# environment (optional) and installs the platform into it.
# Module dependencies are installed separately: benchmark-platform deps install <module>
#
# Environment:
#   CREATE_VENV=false   install into the active Python environment instead of .venv
#   INSTALL_DEV=true    also install the development dependencies (requirements-dev.txt)
#   PYTHON, VENV_DIR    interpreter used to create the venv, and its location
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-${ROOT_DIR}/.venv}"
PYTHON="${PYTHON:-python3}"
INSTALL_DEV="${INSTALL_DEV:-false}"
CREATE_VENV="${CREATE_VENV:-true}"

cd "${ROOT_DIR}"

if ! command -v "${PYTHON}" >/dev/null 2>&1; then
  echo "[ERROR] ${PYTHON} not found: install Python 3 first." >&2
  exit 1
fi

if [[ "${CREATE_VENV}" == "true" ]]; then
  echo "=== Creating Python virtual environment ==="
  if [[ ! -d "${VENV_DIR}" ]]; then
    "${PYTHON}" -m venv "${VENV_DIR}"
    echo "Created virtual environment: ${VENV_DIR}"
  else
    echo "Using existing virtual environment: ${VENV_DIR}"
  fi
  PY="${VENV_DIR}/bin/python"
else
  echo "=== CREATE_VENV=false: installing into the active Python environment ==="
  PY="${PYTHON}"
fi

echo
echo "=== Installing the platform ==="
"${PY}" -m pip install --upgrade pip
"${PY}" -m pip install -e .

if [[ "${INSTALL_DEV}" == "true" ]]; then
  "${PY}" -m pip install -r requirements-dev.txt
fi

echo
echo "Setup complete."
if [[ "${CREATE_VENV}" == "true" ]]; then
  echo "Activate the environment with: source .venv/bin/activate"
fi
echo "Then install the dependencies of the modules you use, e.g.: benchmark-platform deps install envs.kind"

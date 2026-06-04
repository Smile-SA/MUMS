#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-${ROOT_DIR}/.venv}"
PYTHON="${PYTHON:-python3}"
INSTALL_DEV="${INSTALL_DEV:-false}"

cd "${ROOT_DIR}"

echo "=== Checking host prerequisites ==="
./scripts/check_prereqs.sh --skip-python-imports

echo
echo "=== Creating Python virtual environment ==="
if [[ ! -d "${VENV_DIR}" ]]; then
  "${PYTHON}" -m venv "${VENV_DIR}"
  echo "Created virtual environment: ${VENV_DIR}"
else
  echo "Using existing virtual environment: ${VENV_DIR}"
fi

echo
echo "=== Installing Python dependencies ==="
"${VENV_DIR}/bin/python" -m pip install --upgrade pip

if [[ "${INSTALL_DEV}" == "true" ]]; then
  "${VENV_DIR}/bin/python" -m pip install -r requirements-dev.txt
else
  "${VENV_DIR}/bin/python" -m pip install -r requirements.txt
fi

echo
echo "=== Validating installed environment ==="
./scripts/check_prereqs.sh

echo
echo "Setup complete."
echo "Activate the environment with:"
echo "  source .venv/bin/activate"
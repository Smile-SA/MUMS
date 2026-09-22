#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-${ROOT_DIR}/.venv}"
PYTHON="${PYTHON:-python3}"
INSTALL_DEV="${INSTALL_DEV:-false}"
# venv creation is a convenience, not a requirement — set CREATE_VENV=false to
# install into whatever Python environment is already active instead.
CREATE_VENV="${CREATE_VENV:-true}"

cd "${ROOT_DIR}"

echo "=== Checking setup prerequisites ==="
./scripts/check_prereqs.sh --mode setup --skip-python-imports

if [[ "${CREATE_VENV}" == "true" ]]; then
  echo
  echo "=== Creating Python virtual environment ==="
  if [[ ! -d "${VENV_DIR}" ]]; then
    "${PYTHON}" -m venv "${VENV_DIR}"
    echo "Created virtual environment: ${VENV_DIR}"
  else
    echo "Using existing virtual environment: ${VENV_DIR}"
  fi
  PY="${VENV_DIR}/bin/python"
else
  echo
  echo "=== CREATE_VENV=false: installing into the active Python environment ==="
  PY="${PYTHON}"
fi

echo
echo "=== Installing Python dependencies ==="
"${PY}" -m pip install --upgrade pip

"${PY}" -m pip install -e .

if [[ "${INSTALL_DEV}" == "true" ]]; then
  "${PY}" -m pip install -r requirements-dev.txt
fi

echo
echo "=== Validating Python environment ==="
./scripts/check_prereqs.sh --mode setup

echo
echo "Setup complete."
echo

if [[ "${CREATE_VENV}" == "true" ]]; then
  echo "Activate the environment with:"
  echo "  source .venv/bin/activate"
  echo
fi

echo "To check benchmark runtime tools, run:"
echo "  make doctor"
echo
echo "On Ubuntu/Debian, missing runtime tools can be installed with:"
echo "  make install-system-deps-ubuntu"
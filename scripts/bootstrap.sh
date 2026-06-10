#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-${ROOT_DIR}/.venv}"
PYTHON="${PYTHON:-python3}"
INSTALL_DEV="${INSTALL_DEV:-false}"

cd "${ROOT_DIR}"

echo "=== Checking setup prerequisites ==="
./scripts/check_prereqs.sh --mode setup --skip-python-imports

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
echo "=== Validating Python environment ==="
./scripts/check_prereqs.sh --mode setup

echo
echo "Setup complete."
echo
echo "Activate the environment with:"
echo "  source .venv/bin/activate"
echo
echo "To check benchmark runtime tools, run:"
echo "  make doctor"
echo
echo "On Ubuntu/Debian, missing runtime tools can be installed with:"
echo "  make install-system-deps-ubuntu"
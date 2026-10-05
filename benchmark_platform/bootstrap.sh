#!/usr/bin/env bash
# Installs the benchmark platform (its core) into a Python virtual environment
# (created if missing), or into the active Python environment (--no-venv).
# Module dependencies are installed separately: benchmark-platform deps install <module>
#
# Usage: bootstrap.sh [--no-venv] [--venv-dir DIR] [--dev] [--no-shell-profile] [--help]
#   --no-venv           install into the active Python environment, without a venv
#                       (at your own risk: the venv avoids interfering with the rest)
#   --venv-dir DIR      the venv to use, created if missing (default: <repository>/.venv)
#   --dev               also install the development dependencies (requirements-dev.txt)
#   --no-shell-profile  do not touch the shell's profile (only print what to add)
#
# Environment: PYTHON, the interpreter used to create the venv (or, with
# --no-venv, to install into; default: python3).
#
# Writes the settings to the platform's configuration file (module_paths,
# utils_path, and with a venv env: its activate script, sourced by the core at the
# start of every command), unless already in the file (then kept); see
# `benchmark-platform config`. With a venv, also links
# ~/.local/bin/benchmark-platform to it, and puts ~/.local/bin on PATH in the
# shell's profile if needed.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
USE_VENV=true
VENV_DIR="${ROOT_DIR}/.venv"
INSTALL_DEV=false
UPDATE_SHELL_PROFILE=true

usage() { sed -n '2,/^set -euo/p' "${BASH_SOURCE[0]}" | sed '$d; s/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-venv)          USE_VENV=false; shift ;;
    --venv-dir)         [[ $# -ge 2 ]] || { echo "[ERROR] --venv-dir needs a directory" >&2; exit 2; }
                        VENV_DIR="$(realpath -m "$2")"; shift 2 ;;
    --dev)              INSTALL_DEV=true; shift ;;
    --no-shell-profile) UPDATE_SHELL_PROFILE=false; shift ;;
    -h|--help)          usage; exit 0 ;;
    *)                  echo "[ERROR] unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
done

cd "${ROOT_DIR}"

if ! command -v "${PYTHON}" >/dev/null 2>&1; then
  echo "[ERROR] ${PYTHON} not found: install Python 3 first." >&2
  exit 1
fi

if [[ "${USE_VENV}" == "true" ]]; then
  echo "=== Python virtual environment ==="
  if [[ ! -d "${VENV_DIR}" ]]; then
    "${PYTHON}" -m venv "${VENV_DIR}"
    echo "Created virtual environment: ${VENV_DIR}"
  else
    echo "Using existing virtual environment: ${VENV_DIR}"
  fi
  PY="${VENV_DIR}/bin/python"
else
  echo "=== --no-venv: installing into the active Python environment ==="
  PY="${PYTHON}"
fi

echo
echo "=== Installing the platform ==="
"${PY}" -m pip install --upgrade pip
"${PY}" -m pip install -e .

if [[ "${INSTALL_DEV}" == "true" ]]; then
  "${PY}" -m pip install -r requirements-dev.txt
fi

# Settings (where modules and utils are, the environment everything runs in),
# in the platform's configuration file (see `benchmark-platform config`). A
# setting already in the file is kept as is (an environment variable only
# overrides it for one command: it is not taken into account here).
cli() { "${PY}" -c 'import sys; from benchmark_platform.cli import main; sys.exit(main(sys.argv[1:]))' "$@"; }

echo
SETTINGS=("module_paths=${ROOT_DIR}/modules" "utils_path=${ROOT_DIR}/utils")
if [[ "${USE_VENV}" == "true" ]]; then
  # Everything the platform runs goes through the venv, without activating it
  # in the terminal.
  SETTINGS+=("env=${VENV_DIR}/bin/activate")
fi
# Looked up in the file itself (environment variables are only overrides).
CONFIG_FILE="${BENCHMARK_CONFIG:-${XDG_CONFIG_HOME:-${HOME}/.config}/benchmark-platform/config.yaml}"
for pair in "${SETTINGS[@]}"; do
  key="${pair%%=*}"
  if [[ -f "${CONFIG_FILE}" ]] && grep -q "^${key}:" "${CONFIG_FILE}"; then
    echo "${key} already in ${CONFIG_FILE}, kept."
  else
    cli config set "${key}" "${pair#*=}"
  fi
done

# The CLI, callable from anywhere without activating the venv.
if [[ "${USE_VENV}" == "true" ]]; then
  mkdir -p "${HOME}/.local/bin"
  ln -sf "${VENV_DIR}/bin/benchmark-platform" "${HOME}/.local/bin/benchmark-platform"
  echo "Command linked: ${HOME}/.local/bin/benchmark-platform -> ${VENV_DIR}/bin/benchmark-platform"
fi

# ~/.local/bin on PATH (like `pipx ensurepath`), in a marked block of the shell's
# profile, replaced on each run (an older block of this script is removed).
# --no-shell-profile only prints what to add.
BEGIN_MARK="# >>> benchmark-platform >>>"
END_MARK="# <<< benchmark-platform <<<"
case "$(basename "${SHELL:-bash}")" in
  zsh) PROFILE="${HOME}/.zshrc" ;;
  *)   PROFILE="${HOME}/.bashrc" ;;
esac
LINE='export PATH="${HOME}/.local/bin:${PATH}"'
NEEDS_PATH=false
if [[ "${USE_VENV}" == "true" ]]; then
  case ":${PATH}:" in
    *":${HOME}/.local/bin:"*)
      # Already on PATH, maybe thanks to our own block: keep that block then.
      if [[ -f "${PROFILE}" ]] && sed -n "/^${BEGIN_MARK}\$/,/^${END_MARK}\$/p" "${PROFILE}" \
          | grep -qF "${LINE}"; then
        NEEDS_PATH=true
      fi ;;
    *) NEEDS_PATH=true ;;
  esac
fi
if [[ "${UPDATE_SHELL_PROFILE}" == "true" ]]; then
  if [[ -f "${PROFILE}" ]]; then
    sed -i "/^${BEGIN_MARK}\$/,/^${END_MARK}\$/d" "${PROFILE}"
  fi
  if [[ "${NEEDS_PATH}" == "true" ]]; then
    printf '%s\n%s\n%s\n' "${BEGIN_MARK}" "${LINE}" "${END_MARK}" >> "${PROFILE}"
    echo "~/.local/bin on PATH, in ${PROFILE}."
  fi
elif [[ "${NEEDS_PATH}" == "true" ]]; then
  echo "[WARNING] --no-shell-profile: add to your shell's profile: ${LINE}"
fi

echo
echo "Setup complete. Open a new terminal, then check:"
echo "    benchmark-platform config      # module_paths, utils_path, env"
echo "    benchmark-platform doctor"
echo "Then install the dependencies of the modules you use, e.g.: benchmark-platform deps install kind"

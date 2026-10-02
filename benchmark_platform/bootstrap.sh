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
#   --no-shell-profile  do not write BENCHMARK_MODULE_PATHS and BENCHMARK_UTILS_PATH
#                       to the shell's profile, only print them
#
# Environment: PYTHON, the interpreter used to create the venv (or, with
# --no-venv, to install into; default: python3).
#
# Writes BENCHMARK_MODULE_PATHS and BENCHMARK_UTILS_PATH (where modules and utils
# are) to the shell's profile (~/.bashrc, or ~/.zshrc for zsh), in a marked block
# replaced on each run, unless they are already set (then kept and shown).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${PYTHON:-python3}"
USE_VENV=true
VENV_DIR="${ROOT_DIR}/.venv"
INSTALL_DEV=false
UPDATE_SHELL_PROFILE=true

usage() { sed -n '2,19p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

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

echo
echo "Setup complete."
if [[ "${USE_VENV}" == "true" ]]; then
  echo "Activate the environment with: source ${VENV_DIR}/bin/activate"
fi
echo "Then install the dependencies of the modules you use, e.g.: benchmark-platform deps install envs.kind"

# Where modules and utils are: the only sources of truth, read by the core.
# A variable already set is kept as is. The missing ones are written to the
# shell's profile (between markers, replaced on each run), so that every new
# shell has them. --no-shell-profile only prints them.
BEGIN_MARK="# >>> benchmark-platform >>>"
END_MARK="# <<< benchmark-platform <<<"
case "$(basename "${SHELL:-bash}")" in
  zsh) PROFILE="${HOME}/.zshrc" ;;
  *)   PROFILE="${HOME}/.bashrc" ;;
esac

echo
EXPORTS=""
for pair in "BENCHMARK_MODULE_PATHS=${ROOT_DIR}/modules" "BENCHMARK_UTILS_PATH=${ROOT_DIR}/utils"; do
  name="${pair%%=*}"
  if [[ -n "${!name:-}" ]]; then
    echo "${name} already set, kept: ${!name}"
  else
    EXPORTS+="export ${name}=\"${pair#*=}\""$'\n'
  fi
done

if [[ -z "${EXPORTS}" ]]; then
  :
elif [[ "${UPDATE_SHELL_PROFILE}" == "true" ]]; then
  touch "${PROFILE}"
  # Keep the lines of a previous block that are not rewritten, then replace the
  # block: one block, whatever the number of runs.
  KEPT="$(sed -n "/^${BEGIN_MARK}\$/,/^${END_MARK}\$/p" "${PROFILE}" | grep '^export ' || true)"
  for name in $(printf '%s' "${EXPORTS}" | sed -n 's/^export \([A-Z_]*\)=.*/\1/p'); do
    KEPT="$(printf '%s\n' "${KEPT}" | grep -v "^export ${name}=" || true)"
  done
  sed -i "/^${BEGIN_MARK}\$/,/^${END_MARK}\$/d" "${PROFILE}"
  {
    echo "${BEGIN_MARK}"
    [[ -n "${KEPT}" ]] && printf '%s\n' "${KEPT}"
    printf '%s' "${EXPORTS}"
    echo "${END_MARK}"
  } >> "${PROFILE}"
  echo "Written to ${PROFILE}:"
  printf '%s' "${EXPORTS}" | sed 's/^/    /'
  echo "Every new terminal will have them. This terminal was opened before:"
  echo "open a new one (or run 'source ${PROFILE}' once)."
else
  echo "[WARNING] --no-shell-profile: add to your shell's profile, then open a new shell:"
  printf '%s' "${EXPORTS}" | sed 's/^/    /'
fi

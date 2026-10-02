#!/usr/bin/env bash
# Installs the benchmark platform (its core): creates a Python virtual
# environment (optional) and installs the platform into it.
# Module dependencies are installed separately: benchmark-platform deps install <module>
#
# Environment:
#   CREATE_VENV=false   install into the active Python environment instead of .venv
#   INSTALL_DEV=true    also install the development dependencies (requirements-dev.txt)
#   PYTHON, VENV_DIR    interpreter used to create the venv, and its location
#
#   UPDATE_SHELL_PROFILE=false  do not write BENCHMARK_MODULE_PATHS and
#                       BENCHMARK_UTILS_PATH to the shell's profile (only print them)
#
# Writes BENCHMARK_MODULE_PATHS and BENCHMARK_UTILS_PATH (where modules and utils
# are) to the shell's profile (~/.bashrc, or ~/.zshrc for zsh), in a marked block
# replaced on each run, unless they are already set (then kept and shown).
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

# Where modules and utils are: the only sources of truth, read by the core.
# A variable already set is kept as is. The missing ones are written to the
# shell's profile (between markers, replaced on each run), so that every new
# shell has them. UPDATE_SHELL_PROFILE=false only prints them.
BEGIN_MARK="# >>> benchmark-platform >>>"
END_MARK="# <<< benchmark-platform <<<"
case "$(basename "${SHELL:-bash}")" in
  zsh) PROFILE="${HOME}/.zshrc" ;;
  *)   PROFILE="${HOME}/.bashrc" ;;
esac

echo
EXPORTS=""
for pair in "BENCHMARK_MODULE_PATHS=${ROOT_DIR}" "BENCHMARK_UTILS_PATH=${ROOT_DIR}/utils"; do
  name="${pair%%=*}"
  if [[ -n "${!name:-}" ]]; then
    echo "${name} already set, kept: ${!name}"
  else
    EXPORTS+="export ${name}=\"${pair#*=}\""$'\n'
  fi
done

if [[ -z "${EXPORTS}" ]]; then
  :
elif [[ "${UPDATE_SHELL_PROFILE:-true}" == "true" ]]; then
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
  echo "[WARNING] UPDATE_SHELL_PROFILE=false: add to your shell's profile, then open a new shell:"
  printf '%s' "${EXPORTS}" | sed 's/^/    /'
fi

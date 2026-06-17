#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-${ROOT_DIR}/.venv}"
MODE="all"
SKIP_PYTHON_IMPORTS=false

usage() {
  cat <<USAGE
Usage: $0 [--mode setup|runtime|all] [--skip-python-imports]

Check prerequisites required by the benchmark platform.

Modes:
  setup    Check only what is required to create the Python environment.
  runtime  Check external tools required to run the benchmark platform.
  all      Check setup + runtime requirements. Default.

Options:
  --skip-python-imports  Do not validate installed Python packages.
  -h, --help             Show this help message.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode)
      MODE="${2:?Missing value for --mode}"
      shift 2
      ;;
    --mode=*)
      MODE="${1#--mode=}"
      shift
      ;;
    --skip-python-imports)
      SKIP_PYTHON_IMPORTS=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

case "${MODE}" in
  setup|runtime|all)
    ;;
  *)
    echo "[ERROR] Invalid mode: ${MODE}" >&2
    usage >&2
    exit 2
    ;;
esac

ERRORS=0

ok() {
  printf '[OK] %s\n' "$1"
}

warn() {
  printf '[WARN] %s\n' "$1" >&2
}

error() {
  printf '[ERROR] %s\n' "$1" >&2
  ERRORS=$((ERRORS + 1))
}

check_command() {
  local command_name="$1"
  if command -v "${command_name}" >/dev/null 2>&1; then
    ok "Found ${command_name}: $(command -v "${command_name}")"
  else
    error "Missing required command: ${command_name}"
  fi
}

echo "=== Benchmark platform prerequisite check (${MODE}) ==="

setup_commands=(
  bash
  python3
)

runtime_commands=(
  curl
  docker
  git
  helm
  jq
  kind
  kubectl
)

if [[ "${MODE}" == "setup" || "${MODE}" == "all" ]]; then
  echo
  echo "--- Setup prerequisites ---"
  for required_command in "${setup_commands[@]}"; do
    check_command "${required_command}"
  done
fi

if [[ "${MODE}" == "runtime" || "${MODE}" == "all" ]]; then
  echo
  echo "--- Runtime prerequisites ---"
  for required_command in "${runtime_commands[@]}"; do
    check_command "${required_command}"
  done
fi

echo
echo "=== Tool versions ==="

if command -v python3 >/dev/null 2>&1; then
  python3 --version || true
fi

if [[ "${MODE}" == "runtime" || "${MODE}" == "all" ]]; then
  if command -v docker >/dev/null 2>&1; then
    docker --version || true
    if docker info >/dev/null 2>&1; then
      ok "Docker daemon is reachable by the current user."
    else
      error "Docker is installed but the daemon is not reachable by the current user. Start Docker or fix Docker permissions."
    fi
  fi

  if command -v kind >/dev/null 2>&1; then
    kind version || true
  fi

  if command -v kubectl >/dev/null 2>&1; then
    kubectl version --client=true 2>/dev/null || kubectl version --client 2>/dev/null || true
  fi

  if command -v helm >/dev/null 2>&1; then
    helm version --short 2>/dev/null || helm version || true
  fi

  if command -v jq >/dev/null 2>&1; then
    jq --version || true
  fi
fi

echo
echo "=== Host information relevant to Kind validation ==="

if [[ -d /sys/fs/cgroup ]]; then
  CGROUP_FS="$(stat -fc %T /sys/fs/cgroup 2>/dev/null || echo unknown)"
  case "${CGROUP_FS}" in
    cgroup2fs)
      ok "Detected cgroup v2."
      ;;
    tmpfs)
      warn "Detected cgroup v1. Use an explicit compatible Kind node image, for example kindest/node:v1.34.0."
      ;;
    *)
      warn "Could not identify cgroup mode reliably: ${CGROUP_FS}"
      ;;
  esac
fi

if [[ "${SKIP_PYTHON_IMPORTS}" == "false" && ( "${MODE}" == "setup" || "${MODE}" == "all" ) ]]; then
  echo
  echo "=== Python virtual environment dependencies ==="

  if [[ ! -x "${VENV_DIR}/bin/python" ]]; then
    error "Virtual environment not found at ${VENV_DIR}. Run 'make setup' first."
  else
    if "${VENV_DIR}/bin/python" - <<'PY'
import importlib

required_modules = ("locust", "faker", "requests")
missing = []

for module_name in required_modules:
    try:
        importlib.import_module(module_name)
    except ImportError:
        missing.append(module_name)

if missing:
    raise SystemExit(f"Missing Python modules in virtual environment: {', '.join(missing)}")

print("[OK] Runtime Python dependencies are importable.")
PY
    then
      :
    else
      error "Python runtime dependency validation failed. Run 'make setup' again."
    fi
  fi
fi

echo
if [[ "${ERRORS}" -gt 0 ]]; then
  echo "Prerequisite check failed with ${ERRORS} error(s)." >&2

  if [[ "${MODE}" == "runtime" || "${MODE}" == "all" ]]; then
    cat >&2 <<'HINT'

Missing runtime tools can be installed manually, or on Ubuntu/Debian with:

  make install-system-deps-ubuntu

Then rerun:

  make doctor
HINT
  fi

  exit 1
fi

echo "Prerequisite check succeeded."
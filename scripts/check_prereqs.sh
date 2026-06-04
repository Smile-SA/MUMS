#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-${ROOT_DIR}/.venv}"
SKIP_PYTHON_IMPORTS=false

usage() {
  cat <<USAGE
Usage: $0 [--skip-python-imports]

Check system prerequisites required by the benchmark platform.

Options:
  --skip-python-imports  Check host tools only; do not require the local
                         Python virtual environment or installed packages.
  -h, --help             Show this help message.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
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

echo "=== Benchmark platform prerequisite check ==="

required_commands=(
  bash
  curl
  docker
  git
  helm
  jq
  kind
  kubectl
  python3
)

for required_command in "${required_commands[@]}"; do
  check_command "${required_command}"
done

echo
echo "=== Tool versions ==="

if command -v python3 >/dev/null 2>&1; then
  python3 --version || true
fi

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

echo
echo "=== Host information relevant to later Kind validation ==="

if [[ -d /sys/fs/cgroup ]]; then
  CGROUP_FS="$(stat -fc %T /sys/fs/cgroup 2>/dev/null || echo unknown)"
  case "${CGROUP_FS}" in
    cgroup2fs)
      ok "Detected cgroup v2."
      ;;
    tmpfs)
      warn "Detected cgroup v1. The Kind node image must be selected carefully; Kubernetes v1.35 failed on this mode during manual platform testing. Detailed handling belongs to the standalone-deployment issue."
      ;;
    *)
      warn "Could not identify cgroup mode reliably: ${CGROUP_FS}"
      ;;
  esac
fi

if [[ "${SKIP_PYTHON_IMPORTS}" == "false" ]]; then
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
  exit 1
fi

echo "Prerequisite check succeeded."
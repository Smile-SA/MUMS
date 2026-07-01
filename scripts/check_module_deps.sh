#!/usr/bin/env bash
set -euo pipefail

# Validate dependencies for one benchmark-platform module.
#
# Usage:
#   ./scripts/check_module_deps.sh <module_dir>
#
# Checks:
#   - module directory exists
#   - module.yaml is parseable when present
#   - declared commands exist on PATH
#   - declared utils/modules are recursively checked
#   - requirements.txt files are syntactically visible, but not installed
#
# Supported module.yaml fields:
#
# dependencies:
#   commands:
#     - kubectl
#     - helm
#   utils:
#     - utils/helm
#     - utils/scraper
#   modules:
#     - observability/prometheus

usage() {
    cat >&2 <<USAGE
Usage: $0 <module_dir>

Examples:
  $0 envs/kind
  $0 stacks/online-boutique
  $0 observability/prometheus
  $0 traffic/online-boutique
USAGE
}

if [ "$#" -ne 1 ]; then
    usage
    exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd -P)"

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

VISITED_MODULES="${VISITED_MODULES:-}"

normalize_module_dir() {
    local module_dir="$1"

    if [ -d "${module_dir}" ]; then
        (cd "${module_dir}" && pwd -P)
        return 0
    fi

    if [ -d "${REPO_ROOT}/${module_dir}" ]; then
        (cd "${REPO_ROOT}/${module_dir}" && pwd -P)
        return 0
    fi

    echo "[ERROR] Module directory not found: ${module_dir}" >&2
    exit 1
}

relative_to_repo() {
    local path="$1"
    case "${path}" in
        "${REPO_ROOT}"/*) echo "${path#"${REPO_ROOT}/"}" ;;
        *) echo "${path}" ;;
    esac
}

is_visited() {
    local module_abs="$1"
    case ":${VISITED_MODULES}:" in
        *":${module_abs}:"*) return 0 ;;
        *) return 1 ;;
    esac
}

mark_visited() {
    local module_abs="$1"
    if [ -z "${VISITED_MODULES}" ]; then
        VISITED_MODULES="${module_abs}"
    else
        VISITED_MODULES="${VISITED_MODULES}:${module_abs}"
    fi
    export VISITED_MODULES
}

module_yaml_values() {
    local module_yaml="$1"
    local key="$2"

    "${PYTHON_BIN}" - "$module_yaml" "$key" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("[ERROR] PyYAML is required to parse module.yaml.", file=sys.stderr)
    sys.exit(1)

path = Path(sys.argv[1])
key = sys.argv[2]

data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
if not isinstance(data, dict):
    print(f"[ERROR] Invalid module descriptor: {path}", file=sys.stderr)
    sys.exit(1)

deps = data.get("dependencies", {})
if not isinstance(deps, dict):
    sys.exit(0)

value = deps.get(key, [])
if isinstance(value, str):
    print(value)
elif isinstance(value, list):
    for item in value:
        if isinstance(item, str):
            print(item)
PY
}

check_module() {
    local module_input="$1"
    local module_abs
    module_abs="$(normalize_module_dir "${module_input}")"

    if is_visited "${module_abs}"; then
        return 0
    fi
    mark_visited "${module_abs}"

    local module_rel
    module_rel="$(relative_to_repo "${module_abs}")"

    echo "=== Checking module dependencies: ${module_rel} ==="

    local module_yaml="${module_abs}/module.yaml"
    if [ ! -f "${module_yaml}" ]; then
        echo "[WARN] No module.yaml found in ${module_rel}."
    else
        echo "    Descriptor: ${module_rel}/module.yaml"

        # Parse once to fail early if malformed.
        "${PYTHON_BIN}" - "$module_yaml" <<'PY'
from __future__ import annotations
import sys
from pathlib import Path
import yaml
path = Path(sys.argv[1])
data = yaml.safe_load(path.read_text(encoding="utf-8"))
if not isinstance(data, dict):
    raise SystemExit(f"Invalid YAML module descriptor: {path}")
for required in ("name", "type"):
    if required not in data:
        raise SystemExit(f"Missing required module.yaml field: {required} in {path}")
PY

        while IFS= read -r command_name; do
            [ -n "${command_name}" ] || continue
            if ! command -v "${command_name}" >/dev/null 2>&1; then
                echo "[ERROR] Missing command for ${module_rel}: ${command_name}" >&2
                exit 1
            fi
            echo "    Command OK: ${command_name}"
        done < <(module_yaml_values "${module_yaml}" commands)

        while IFS= read -r dependency; do
            [ -n "${dependency}" ] || continue
            check_module "${dependency}"
        done < <(module_yaml_values "${module_yaml}" utils)

        while IFS= read -r dependency; do
            [ -n "${dependency}" ] || continue
            check_module "${dependency}"
        done < <(module_yaml_values "${module_yaml}" modules)
    fi

    if [ -f "${module_abs}/requirements.txt" ]; then
        echo "    Python requirements declared: ${module_rel}/requirements.txt"
    fi

    if [ -f "${module_abs}/dependencies.sh" ]; then
        echo "    Additional dependency script declared: ${module_rel}/dependencies.sh"
        bash -n "${module_abs}/dependencies.sh"
    fi

    echo "=== Module dependency check OK: ${module_rel} ==="
}

check_module "$1"

#!/usr/bin/env bash
set -euo pipefail

# Install Python/system helper dependencies for one benchmark-platform module.
#
# Usage:
#   ./scripts/install_module_deps.sh <module_dir>
#
# Examples:
#   ./scripts/install_module_deps.sh traffic/online-boutique
#   ./scripts/install_module_deps.sh observability/prometheus
#   ./scripts/install_module_deps.sh utils/scraper
#
# Supported module files:
#   <module_dir>/requirements.txt
#   <module_dir>/dependencies.sh
#   <module_dir>/module.yaml
#
# Supported module.yaml fields:
#
#   dependencies:
#     utils:
#       - utils/scraper
#       - utils/prometheus
#
#   dependencies:
#     modules:
#       - observability/prometheus
#
# The script installs dependencies recursively and avoids installing the same
# module twice in one invocation.

usage() {
    cat >&2 <<USAGE
Usage: $0 <module_dir>

Install dependencies for a benchmark-platform module.

Examples:
  $0 traffic/online-boutique
  $0 observability/prometheus
  $0 utils/scraper
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
    echo "        Create the virtual environment first, or set PYTHON_BIN." >&2
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

relative_to_repo() {
    local path="$1"

    case "${path}" in
        "${REPO_ROOT}"/*)
            echo "${path#"${REPO_ROOT}/"}"
            ;;
        *)
            echo "${path}"
            ;;
    esac
}

module_dependencies_from_yaml() {
    local module_yaml="$1"

    "${PYTHON_BIN}" - "$module_yaml" <<'PY'
from __future__ import annotations

import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print(
        "[WARN] PyYAML is not installed; cannot parse module.yaml dependencies.",
        file=sys.stderr,
    )
    sys.exit(0)

path = Path(sys.argv[1])
data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}

dependencies = data.get("dependencies", {})
result: list[str] = []


def extend_from(value: object) -> None:
    if value is None:
        return
    if isinstance(value, str):
        result.append(value)
        return
    if isinstance(value, list):
        for item in value:
            if isinstance(item, str):
                result.append(item)


if isinstance(dependencies, dict):
    extend_from(dependencies.get("utils"))
    extend_from(dependencies.get("modules"))

# Optional shorthand, useful during migration:
extend_from(data.get("utils"))
extend_from(data.get("modules"))

for dependency in dict.fromkeys(result):
    print(dependency)
PY
}

install_module() {
    local module_input="$1"
    local module_abs
    module_abs="$(normalize_module_dir "${module_input}")"

    if is_visited "${module_abs}"; then
        echo "=== Skipping already processed module: $(relative_to_repo "${module_abs}") ==="
        return 0
    fi

    mark_visited "${module_abs}"

    local module_rel
    module_rel="$(relative_to_repo "${module_abs}")"

    echo "=== Installing module dependencies: ${module_rel} ==="

    local module_yaml="${module_abs}/module.yaml"

    if [ -f "${module_yaml}" ]; then
        echo "    Reading module descriptor: ${module_rel}/module.yaml"

        while IFS= read -r dependency; do
            [ -n "${dependency}" ] || continue
            echo "    Installing declared dependency: ${dependency}"
            install_module "${dependency}"
        done < <(module_dependencies_from_yaml "${module_yaml}")
    fi

    local requirements_file="${module_abs}/requirements.txt"

    if [ -f "${requirements_file}" ]; then
        echo "    Installing Python requirements: ${module_rel}/requirements.txt"
        "${PYTHON_BIN}" -m pip install -r "${requirements_file}"
    else
        echo "    No requirements.txt found."
    fi

    local dependencies_script="${module_abs}/dependencies.sh"

    if [ -f "${dependencies_script}" ]; then
        echo "    Running dependency script: ${module_rel}/dependencies.sh"
        bash "${dependencies_script}"
    else
        echo "    No dependencies.sh found."
    fi

    echo "=== Module dependencies installed: ${module_rel} ==="
}

install_module "$1"

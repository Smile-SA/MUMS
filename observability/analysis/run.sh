#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd -P)"
ACTION="${1:-}"
shift || true

PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || true)}"

case "${ACTION}" in
  process)
    RUN_OUTPUT_DIR="${1:-}"
    shift || true

    if [ -z "${RUN_OUTPUT_DIR}" ]; then
      echo "Usage: $0 process <run_output_dir> [--lines=N]" >&2
      exit 2
    fi

    METRICS_FILE="${RUN_OUTPUT_DIR}/metrics/metrics.om"
    OUTPUT_DIR="${RUN_OUTPUT_DIR}/post-processing"

    if [ ! -s "${METRICS_FILE}" ]; then
      echo "[SKIP] Metrics file is missing or empty: ${METRICS_FILE}" >&2
      exit 0
    fi

    cat "${METRICS_FILE}" | "${SCRIPT_DIR}/run_all.sh" "${OUTPUT_DIR}" "$@"

    if [ -n "${PYTHON_BIN}" ]; then
      echo "=== Writing post-processing metadata ===" >&2
      "${PYTHON_BIN}" "${SCRIPT_DIR}/metadata.py" "${RUN_OUTPUT_DIR}"
    fi
    ;;

  help|-h|--help|"")
    echo "Usage: $0 process <run_output_dir> [--lines=N]" >&2
    ;;

  *)
    echo "[ERROR] Unsupported post-processing action: ${ACTION}" >&2
    exit 2
    ;;
esac
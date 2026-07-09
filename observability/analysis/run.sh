#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd -P)"
ACTION="${1:-}"
shift || true

PYTHON_BIN="${PYTHON_BIN:-$(command -v python3 || true)}"

case "${ACTION}" in
  generate)
    METRICS_FILE="${1:-}"
    OUTPUT_DIR="${2:-}"
    shift 2 || true

    if [ -z "${METRICS_FILE}" ] || [ -z "${OUTPUT_DIR}" ]; then
      echo "Usage: $0 generate <metrics_file> <output_dir> [--lines=N]" >&2
      exit 2
    fi

    if [ ! -s "${METRICS_FILE}" ]; then
      echo "[SKIP] Metrics file is missing or empty: ${METRICS_FILE}" >&2
      exit 0
    fi

    cat "${METRICS_FILE}" | "${SCRIPT_DIR}/run_all.sh" "${OUTPUT_DIR}" "$@"

    if [ -n "${BENCHMARK_RUN_DIR:-}" ] && [ -n "${PYTHON_BIN}" ]; then
      echo "=== Writing dataset metadata ===" >&2
      "${PYTHON_BIN}" -m benchmark_platform.datasets.metadata "${BENCHMARK_RUN_DIR}"
    fi
    ;;
  help|-h|--help|"")
    echo "Usage: $0 generate <metrics_file> <output_dir> [--lines=N]" >&2
    ;;
  *)
    echo "[ERROR] Unsupported dataset action: ${ACTION}" >&2
    exit 2
    ;;
esac

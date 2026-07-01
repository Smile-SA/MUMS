#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ACTION="${1:-}"
shift || true

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
      echo "[ERROR] Metrics file is missing or empty: ${METRICS_FILE}" >&2
      exit 1
    fi

    cat "${METRICS_FILE}" | "${SCRIPT_DIR}/run_all.sh" "${OUTPUT_DIR}" "$@"
    ;;
  help|-h|--help|"")
    echo "Usage: $0 generate <metrics_file> <output_dir> [--lines=N]" >&2
    ;;
  *)
    echo "[ERROR] Unsupported dataset action: ${ACTION}" >&2
    exit 2
    ;;
esac

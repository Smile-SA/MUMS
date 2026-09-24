#!/usr/bin/env bash
# Refined-CSV post-processing module (contract 1): turns the observability
# output (metrics.om, OpenMetrics) into the refined CSV tables (see README.md).
#
# Usage:
#   run.sh run <observability_dir> <traffic_dir> <output_dir> [--csv_lines N]
#
# <traffic_dir> is not used yet.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

usage() {
    echo "Usage: $0 run <observability_dir> <traffic_dir> <output_dir> [--csv_lines N]" >&2
    exit 1
}

ACTION="${1:-}"
if [ "$ACTION" != "run" ]; then
    [ -n "$ACTION" ] && echo "ERROR: unknown action '$ACTION'" >&2
    usage
fi
shift
[ "$#" -ge 3 ] || usage
OBSERVABILITY_DIR="$1"
TRAFFIC_DIR="$2"   # unused for now
OUTPUT_DIR="$3"
shift 3

CSV_LINES=100000
while [ "$#" -gt 0 ]; do
    case "$1" in
        --csv_lines) CSV_LINES="$2"; shift 2 ;;
        *)
            echo "ERROR: unknown option '$1'" >&2
            usage
            ;;
    esac
done

METRICS_FILE="${OBSERVABILITY_DIR}/metrics.om"

if [ ! -s "$METRICS_FILE" ]; then
    echo "[SKIP] Metrics file is missing or empty: ${METRICS_FILE}" >&2
    exit 0
fi

mkdir -p "$OUTPUT_DIR"
"${SCRIPT_DIR}/run_all.sh" "$OUTPUT_DIR" --lines="$CSV_LINES" < "$METRICS_FILE"

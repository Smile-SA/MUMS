#!/usr/bin/env bash
# Essential-tables post-processing module (contract 1): turns the OpenMetrics
# scrapes (<data_dir>/openmetrics/) into tables of the essential data about the
# cluster's objects and their use (<data_dir>/essential-tables/, see README.md).
#
# Usage:
#   run.sh run <data_dir>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
CSV_LINES=100000   # data rows per CSV file (technical detail, not an argument)

usage() {
    echo "Usage: $0 run <data_dir>" >&2
    exit 1
}

ACTION="${1:-}"
if [ "$ACTION" != "run" ]; then
    [ -n "$ACTION" ] && echo "ERROR: unknown action '$ACTION'" >&2
    usage
fi
shift
[ "$#" -eq 1 ] || usage
DATA_DIR="$1"

INPUT_DIR="${DATA_DIR}/openmetrics"
OUTPUT_DIR="${DATA_DIR}/essential-tables"
shopt -s nullglob
SCRAPES=("$INPUT_DIR"/*.om)

if [ "${#SCRAPES[@]}" -eq 0 ]; then
    echo "[SKIP] No OpenMetrics scrape found in ${INPUT_DIR}" >&2
    exit 0
fi

mkdir -p "$OUTPUT_DIR"
cat "${SCRAPES[@]}" | "${SCRIPT_DIR}/run_all.sh" "$OUTPUT_DIR" --lines="$CSV_LINES"

#!/usr/bin/env bash
# Refined-CSV post-processing module (contract 1): turns OpenMetrics scrapes
# (<data_dir>/openmetrics/) into the refined CSV tables (<data_dir>/refined-csv/,
# see README.md).
#
# Usage:
#   run.sh run <data_dir> [--csv_lines N]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"

usage() {
    echo "Usage: $0 run <data_dir> [--csv_lines N]" >&2
    exit 1
}

ACTION="${1:-}"
if [ "$ACTION" != "run" ]; then
    [ -n "$ACTION" ] && echo "ERROR: unknown action '$ACTION'" >&2
    usage
fi
shift
[ "$#" -ge 1 ] || usage
DATA_DIR="$1"
shift

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

# Input: OpenMetrics scrapes (<data_dir>/openmetrics/<index>.om), read in order.
# Output: the refined CSV tables (<data_dir>/refined-csv/).
INPUT_DIR="${DATA_DIR}/openmetrics"
OUTPUT_DIR="${DATA_DIR}/refined-csv"
shopt -s nullglob
SCRAPES=("$INPUT_DIR"/*.om)

if [ "${#SCRAPES[@]}" -eq 0 ]; then
    echo "[SKIP] No OpenMetrics scrape found in ${INPUT_DIR}" >&2
    exit 0
fi

mkdir -p "$OUTPUT_DIR"
cat "${SCRAPES[@]}" | "${SCRIPT_DIR}/run_all.sh" "$OUTPUT_DIR" --lines="$CSV_LINES"

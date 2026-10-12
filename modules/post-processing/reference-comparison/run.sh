#!/usr/bin/env bash
# Post-processing module (contract 1): compares this run's summaries with those
# of a reference run, with the util `compare`, and writes the result as standard
# data: <data_dir>/comparison/reference-comparison.csv (see README.md).
#
# Usage: run.sh run <data_dir> --reference <absolute path to a data directory>

set -euo pipefail

UTILS_DIR="${MUMS_UTILS_PATH:?MUMS_UTILS_PATH is not set}"
OUTPUT_NAME="reference-comparison.csv"

usage() {
    echo "Usage: $0 run <data_dir> --reference <data_dir of the reference run>" >&2
    exit 1
}

[ "${1:-}" = "run" ] || usage
shift
[ "$#" -ge 1 ] || usage
DATA_DIR="$1"
shift

REFERENCE=""
while [ "$#" -gt 0 ]; do
    case "$1" in
        --reference) REFERENCE="${2:-}"; shift 2 ;;
        *) echo "ERROR: unknown option '$1'" >&2; usage ;;
    esac
done

[ -n "$REFERENCE" ] || { echo "ERROR: --reference is required" >&2; exit 1; }
case "$REFERENCE" in
    /*) ;;
    *) echo "ERROR: --reference must be an absolute path: $REFERENCE" >&2; exit 1 ;;
esac
for dir in "$REFERENCE" "$DATA_DIR"; do
    if ! ls "$dir"/summary/*.csv >/dev/null 2>&1; then
        echo "ERROR: no summary in $dir/summary/: run the modules that write" \
             "summaries (before this one, for this run)." >&2
        exit 1
    fi
done

mkdir -p "$DATA_DIR/comparison"
python3 "$UTILS_DIR/compare/compare.py" "$REFERENCE" "$DATA_DIR" \
    -c "$DATA_DIR/comparison/$OUTPUT_NAME"
echo "=== Comparison with the reference written: $DATA_DIR/comparison/$OUTPUT_NAME ==="

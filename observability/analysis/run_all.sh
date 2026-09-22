#!/bin/bash
# run_all.sh
# Generates the 8 analysis CSV files from an OpenMetrics stream on stdin.
#
# Usage:
#   <command> | ./run_all.sh <output_dir> [--lines=N]
#   cat metrics.om | ./run_all.sh output/run-42/post-processing/
#   cat metrics.om | ./run_all.sh output/run-42/post-processing/ --lines=50000
#
# CSVs are split into numbered files (default: 100000 rows/file).
# pod_timeseries.csv is generated last by merging the split files.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT="${1:-}"
CSV_LINES=100000

for arg in "$@"; do
    case $arg in
        --lines=*) CSV_LINES="${arg#--lines=}" ;;
    esac
done

if [ -z "$OUTPUT" ]; then
    echo "Usage: <command> | $0 <output_dir> [--lines=N]" >&2
    exit 1
fi

mkdir -p "$OUTPUT"

# Buffer stdin to a temp file so it can be read multiple times.
TMPFILE="$(mktemp /tmp/openmetrics_XXXXXX.om)"
trap 'rm -f "$TMPFILE"' EXIT

echo "=== Reading OpenMetrics stream ===" >&2
tee "$TMPFILE" > /dev/null

run() {
    local label="$1"
    local script="$2"
    local out_dir="$3"
    echo "=== $label ===" >&2
    python3 "$SCRIPT_DIR/$script" < "$TMPFILE" \
        | "$SCRIPT_DIR/csv_split.sh" "$out_dir" --lines="$CSV_LINES"
}

run "container_timeseries"    container_timeseries.py    "$OUTPUT/container_timeseries"
run "container_metadata"      container_metadata.py      "$OUTPUT/container_metadata"
run "pod_metadata"            pod_metadata.py            "$OUTPUT/pod_metadata"
run "node_timeseries"         node_timeseries.py         "$OUTPUT/node_timeseries"
run "node_metadata"           node_metadata.py           "$OUTPUT/node_metadata"
run "controller_timeseries"   controller_timeseries.py   "$OUTPUT/controller_timeseries"
run "controller_metadata"     controller_metadata.py     "$OUTPUT/controller_metadata"

echo "=== pod_timeseries (aggregating from split directories) ===" >&2
python3 "$SCRIPT_DIR/pod_timeseries.py" \
    <("$SCRIPT_DIR/csv_merge.sh" "$OUTPUT/container_timeseries") \
    <("$SCRIPT_DIR/csv_merge.sh" "$OUTPUT/container_metadata")   \
    <("$SCRIPT_DIR/csv_merge.sh" "$OUTPUT/pod_metadata")         \
    | "$SCRIPT_DIR/csv_split.sh" "$OUTPUT/pod_timeseries" --lines="$CSV_LINES"

echo "=== Done ===" >&2
for dir in "$OUTPUT"/*/; do
    count=$(ls "$dir" | wc -l)
    echo "  $dir : $count file(s)" >&2
done

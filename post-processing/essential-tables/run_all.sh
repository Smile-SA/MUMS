#!/bin/bash
# run_all.sh
# Generates the 8 essential tables from an OpenMetrics stream on stdin.
#
# Usage:
#   <command> | ./run_all.sh <output_dir> [--lines=N]
#   cat <data_dir>/openmetrics/*.om | ./run_all.sh <data_dir>/essential-tables
#
# CSVs are split into numbered files (default: 100000 rows/file).

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

# Buffer stdin to a temp file so it can be read multiple times; tables are
# written whole in a temp directory, then split (pod_timeseries reads 3 of them).
TMPDIR_TABLES="$(mktemp -d "$OUTPUT/.work_XXXXXX")"   # next to the output: /tmp may be too small
TMPFILE="$TMPDIR_TABLES/scrapes.om"
trap 'rm -rf "$TMPDIR_TABLES"' EXIT

echo "=== Reading OpenMetrics stream ===" >&2
cat > "$TMPFILE"

extract() {
    local table="$1"
    echo "=== $table ===" >&2
    python3 "$SCRIPT_DIR/$table.py" < "$TMPFILE" > "$TMPDIR_TABLES/$table.csv"
}

for table in container_timeseries container_metadata pod_metadata node_timeseries \
             node_metadata controller_timeseries controller_metadata; do
    extract "$table"
done

echo "=== pod_timeseries (aggregated from containers) ===" >&2
python3 "$SCRIPT_DIR/pod_timeseries.py" \
    "$TMPDIR_TABLES/container_timeseries.csv" \
    "$TMPDIR_TABLES/container_metadata.csv" \
    "$TMPDIR_TABLES/pod_metadata.csv" \
    > "$TMPDIR_TABLES/pod_timeseries.csv"

for table in container_timeseries container_metadata pod_timeseries pod_metadata \
             node_timeseries node_metadata controller_timeseries controller_metadata; do
    python3 "$SCRIPT_DIR/csv_split.py" "$OUTPUT/$table" --lines="$CSV_LINES" \
        < "$TMPDIR_TABLES/$table.csv"
done

echo "=== Done ===" >&2
for dir in "$OUTPUT"/*/; do
    count=$(ls "$dir" | wc -l)
    echo "  $dir : $count file(s)" >&2
done

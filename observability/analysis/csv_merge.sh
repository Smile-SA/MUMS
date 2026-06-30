#!/bin/bash
# csv_merge.sh
# Concatenates the CSV files in a directory into a single stream on stdout.
#
# Usage: csv_merge.sh <directory>
#
# Reads:  <directory>/<basename>_1.csv
#         <directory>/<basename>_2.csv
#         ...
#
# The header is emitted only once (from the first file).
# Exact inverse of csv_split.sh:
#   cmd | csv_split.sh dir && csv_merge.sh dir | cmd2  ==  cmd | cmd2

set -euo pipefail

DIR="${1:-}"

if [ -z "$DIR" ]; then
    echo "Usage: $0 <directory>" >&2
    exit 1
fi

BASENAME="$(basename "$DIR")"

# Collect files in strict numeric order.
files=()
count=1
while [ -f "$DIR/${BASENAME}_${count}.csv" ]; do
    files+=("$DIR/${BASENAME}_${count}.csv")
    count=$((count + 1))
done

if [ ${#files[@]} -eq 0 ]; then
    echo "ERROR: no files found in $DIR (expected: ${BASENAME}_1.csv ...)" >&2
    exit 1
fi

# First file: full (header + data).
cat "${files[0]}"

# Subsequent files: skip the header (line 1).
for file in "${files[@]:1}"; do
    tail -n +2 "$file"
done

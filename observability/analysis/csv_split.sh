#!/bin/bash
# csv_split.sh
# Reads a CSV from stdin and splits it into numbered files in a directory.
#
# Usage: csv_split.sh <directory> [--lines=N]
#
# Output: <directory>/<basename>_1.csv
#         <directory>/<basename>_2.csv
#         ...
#
# Each output file is a self-contained CSV (header included).
# Default: 100000 data rows per file.

set -euo pipefail

DIR="${1:-}"
CSV_LINES=100000

for arg in "$@"; do
    case $arg in
        --lines=*) CSV_LINES="${arg#--lines=}" ;;
    esac
done

if [ -z "$DIR" ]; then
    echo "Usage: $0 <directory> [--lines=N]" >&2
    exit 1
fi

BASENAME="$(basename "$DIR")"
mkdir -p "$DIR"

awk \
    -v dir="$DIR" \
    -v base="$BASENAME" \
    -v lim="$CSV_LINES" \
'
NR == 1 {
    header  = $0
    count   = 1
    outfile = dir "/" base "_" count ".csv"
    print header > outfile
    next
}
{
    data_nr = NR - 1
    if (data_nr > 1 && (data_nr - 1) % lim == 0) {
        count++
        outfile = dir "/" base "_" count ".csv"
        print header > outfile
    }
    print >> outfile
}
END {
    print "=== Split done: " count " file(s) in " dir > "/dev/stderr"
}
'

#!/bin/bash
# run_all.sh
# Génère les 8 fichiers CSV d'analyse depuis un flux OpenMetrics sur stdin.
#
# Usage :
#   <commande> | ./run_all.sh <output_dir> [--lines=N]
#   cat metrics.om | ./run_all.sh output/test-complet/raffined/
#   cat metrics.om | ./run_all.sh output/test-complet/raffined/ --lines=50000
#
# Les CSV sont splittes en fichiers numérotés (défaut : 100000 lignes/fichier).
# pod_timeseries.csv est généré en dernier depuis les fichiers splittes.

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
    echo "Usage: <commande> | $0 <output_dir> [--lines=N]" >&2
    exit 1
fi

mkdir -p "$OUTPUT"

# Matérialiser stdin dans un tmpfile
TMPFILE="$(mktemp /tmp/openmetrics_XXXXXX.om)"
trap 'rm -f "$TMPFILE"' EXIT

echo "=== Lecture du flux OpenMetrics ===" >&2
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

echo "=== pod_timeseries (agrégation depuis dossiers splittes) ===" >&2
python3 "$SCRIPT_DIR/pod_timeseries.py" \
    <("$SCRIPT_DIR/csv_merge.sh" "$OUTPUT/container_timeseries") \
    <("$SCRIPT_DIR/csv_merge.sh" "$OUTPUT/container_metadata")   \
    <("$SCRIPT_DIR/csv_merge.sh" "$OUTPUT/pod_metadata")         \
    | "$SCRIPT_DIR/csv_split.sh" "$OUTPUT/pod_timeseries" --lines="$CSV_LINES"

echo "=== Terminé ===" >&2
for dir in "$OUTPUT"/*/; do
    count=$(ls "$dir" | wc -l)
    echo "  $dir : $count fichier(s)" >&2
done

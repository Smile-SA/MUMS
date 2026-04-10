#!/bin/bash
# csv_split.sh
# Lit un CSV depuis stdin, découpe en fichiers numérotés dans un dossier.
#
# Usage : csv_split.sh <dossier> [--lines=N]
#
# Produit : <dossier>/<basename>_1.csv
#           <dossier>/<basename>_2.csv
#           ...
#
# Chaque fichier est un CSV valide autonome (header inclus).
# N lignes de données par fichier, défaut : 100000.

set -euo pipefail

DIR="${1:-}"
CSV_LINES=100000

for arg in "$@"; do
    case $arg in
        --lines=*) CSV_LINES="${arg#--lines=}" ;;
    esac
done

if [ -z "$DIR" ]; then
    echo "Usage: $0 <dossier> [--lines=N]" >&2
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
    print "=== Split terminé : " count " fichier(s) dans " dir > "/dev/stderr"
}
'

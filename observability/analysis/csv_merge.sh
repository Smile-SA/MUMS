#!/bin/bash
# csv_merge.sh
# Concatène les fichiers CSV d'un dossier en un seul flux sur stdout.
#
# Usage : csv_merge.sh <dossier>
#
# Lit    : <dossier>/<basename>_1.csv
#          <dossier>/<basename>_2.csv
#          ...
#
# Le header n'est émis qu'une seule fois (depuis le premier fichier).
# Inverse exact de csv_split.sh :
#   cmd | csv_split.sh monDossier && csv_merge.sh monDossier | cmd2
#   == cmd | cmd2

set -euo pipefail

DIR="${1:-}"

if [ -z "$DIR" ]; then
    echo "Usage: $0 <dossier>" >&2
    exit 1
fi

BASENAME="$(basename "$DIR")"

# Collecter les fichiers dans l'ordre numérique strict
files=()
count=1
while [ -f "$DIR/${BASENAME}_${count}.csv" ]; do
    files+=("$DIR/${BASENAME}_${count}.csv")
    count=$((count + 1))
done

if [ ${#files[@]} -eq 0 ]; then
    echo "ERREUR: aucun fichier trouvé dans $DIR (attendu : ${BASENAME}_1.csv ...)" >&2
    exit 1
fi

# Premier fichier : intégral (header + données)
cat "${files[0]}"

# Fichiers suivants : on saute le header (ligne 1)
for file in "${files[@]:1}"; do
    tail -n +2 "$file"
done

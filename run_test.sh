#!/bin/bash
# run_test.sh - exécuter un test complet
# Usage : ./run_test.sh <env_script> <stack_script> <traffic_script> <optimizer_script> <output_dir> [seed] [--option=value ...]

set -e

if [ "$#" -lt 5 ]; then
    echo "Usage: $0 <env_script> <stack_script> <traffic_script> <optimizer_script> <output_dir> [seed] [--option=value ...]"
    exit 1
fi

ENV_SCRIPT=$1
STACK_SCRIPT=$2
TRAFFIC_SCRIPT=$3
OPTIMIZER_SCRIPT=$4
OUTPUT_DIR=$5
SEED=${6:-$(date +%s)}  # seed optionnelle
shift 6  # reste dans "$@" sont les paramètres pass-through

# Créer dossier de sortie si nécessaire
mkdir -p "$OUTPUT_DIR"

echo "=== Créer cluster ==="
KUBECONFIG=$($ENV_SCRIPT create "$SEED" "$@")

# Définir trap uniquement après la création du cluster
cleanup() {
    if [ -n "$KUBECONFIG" ] && [ -f "$KUBECONFIG" ]; then
        echo "=== Une erreur est survenue après la création du cluster, destruction en cours ==="
        $ENV_SCRIPT destroy "$KUBECONFIG" "$SEED" "$@"
    fi
}
trap cleanup ERR

echo "=== Déployer stack ==="
$STACK_SCRIPT "$KUBECONFIG" "$SEED" "$@"

echo "=== Générer trafic ==="
$TRAFFIC_SCRIPT "$KUBECONFIG" "$SEED" "$@"

echo "=== Déployer optimiseur ==="
$OPTIMIZER_SCRIPT "$KUBECONFIG" "$SEED" "$@"

echo "=== Collecte logs ==="
$ENV_SCRIPT collect_logs "$KUBECONFIG" "$SEED" "$OUTPUT_DIR" "$@"

echo "=== Détruire cluster ==="
$ENV_SCRIPT destroy "$KUBECONFIG" "$SEED" "$@"

echo "=== Test terminé. Résultats dans $OUTPUT_DIR ==="

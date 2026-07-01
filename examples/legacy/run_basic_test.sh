#!/bin/bash
# SUPERSEDED — use `benchmark-platform run <config>` instead.
#
# This script was the original orchestrator and is kept here for reference only.
# The canonical entry point is now the CLI:
#
#   benchmark-platform run configs/basic-online-boutique.yaml
#
# or via Make:
#
#   make run-basic
#
# See the project README for the current workflow.
#
# ---------------------------------------------------------------------------
# Exécute un test de bout en bout : env → observabilité → stack → trafic → optimizer → collecte → cleanup.
#
# Usage:
#   ./run_basic_test.sh <env> <observability> <stack> <traffic> <optimizer> <output_dir> \
#       [seed] [--duration=<seconds>] [options...]
#
# Arguments positionnels :
#   env             Script d'environnement  (ex: envs/kind.sh)
#   observability   Script d'observabilité  (ex: utils/prometheus/run.sh)
#   stack           Script de stack         (ex: stacks/online-boutique/deploy.sh)
#   traffic         Script de trafic        (ex: traffic/online-boutique/run.sh)
#   optimizer       Script d'optimiseur     (ex: optimizers/baseline.sh)
#   output_dir      Dossier de sortie       (ex: ./output/run-42)
#   seed            Graine pour la repro    (défaut: 42)
#
# Options :
#   --duration=<s>  Durée du test en secondes (défaut: 300)
#   Toutes les autres options sont passées en pass-through aux sous-scripts.

set -e

# ─── Arguments ────────────────────────────────────────────────────────────────

ENV_SCRIPT=$1
OBSERVABILITY_SCRIPT=$2
STACK_SCRIPT=$3
TRAFFIC_SCRIPT=$4
OPTIMIZER_SCRIPT=$5
OUTPUT_DIR=$6
shift 6

if [ -z "$ENV_SCRIPT" ] || [ -z "$OBSERVABILITY_SCRIPT" ] || [ -z "$STACK_SCRIPT" ] \
    || [ -z "$TRAFFIC_SCRIPT" ] || [ -z "$OPTIMIZER_SCRIPT" ] || [ -z "$OUTPUT_DIR" ]; then
    echo "Usage: $0 <env> <observability> <stack> <traffic> <optimizer> <output_dir> [seed] [--duration=<s>] [options...]" >&2
    exit 1
fi

SEED=42
DURATION=300
EXTRA_ARGS=()

# Le premier arg restant sans '--' est le seed
if [[ -n "$1" && "$1" != --* ]]; then
    SEED=$1
    shift
fi

for arg in "$@"; do
    case $arg in
        --duration=*) DURATION="${arg#--duration=}" ;;
        *)            EXTRA_ARGS+=("$arg") ;;
    esac
done

# ─── Cleanup / trap ───────────────────────────────────────────────────────────

KUBECONFIG=""

CLEANED_UP=false
cleanup() {
    [ "$CLEANED_UP" = true ] && return
    CLEANED_UP=true
    echo "" >&2
    echo "=== Cleanup ===" >&2

    # Trafic
    if [ -n "$KUBECONFIG" ]; then
        echo "--- Arrêt de l'observabilité" >&2
        "$OBSERVABILITY_SCRIPT" stop "$KUBECONFIG" "${EXTRA_ARGS[@]}" || true

        echo "--- Arrêt du trafic" >&2
        "$TRAFFIC_SCRIPT" stop "$KUBECONFIG" "${EXTRA_ARGS[@]}" || true
    fi

    echo "--- Destruction de l'environnement" >&2
    "$ENV_SCRIPT" destroy "$SEED" "${EXTRA_ARGS[@]}" || true

    echo "=== Cleanup terminé" >&2
}

trap 'wait; cleanup' INT
trap cleanup ERR EXIT

# ─── Séquence principale ──────────────────────────────────────────────────────

echo "======================================" >&2
echo "=== run_basic_test.sh               ===" >&2
echo "    Seed     : $SEED" >&2
echo "    Duration : ${DURATION}s" >&2
echo "    Output   : $OUTPUT_DIR" >&2
echo "======================================" >&2

mkdir -p "$OUTPUT_DIR"

# 1. Créer l'environnement
echo "" >&2
echo "=== [1/5] Création de l'environnement ===" >&2
KUBECONFIG=$("$ENV_SCRIPT" create "$SEED" "${EXTRA_ARGS[@]}")
echo "    KUBECONFIG : $KUBECONFIG" >&2

# 2. Démarrer l'observabilité
echo "" >&2
echo "=== [2/5] Démarrage de l'observabilité ===" >&2
"$OBSERVABILITY_SCRIPT" start "$KUBECONFIG" "$OUTPUT_DIR" "${EXTRA_ARGS[@]}"

# 3. Déployer la stack
echo "" >&2
echo "=== [3/5] Déploiement de la stack ===" >&2
"$STACK_SCRIPT" "$KUBECONFIG" "$SEED" "${EXTRA_ARGS[@]}"

# 4. Démarrer le trafic
echo "" >&2
echo "=== [4/5] Démarrage du trafic ===" >&2
"$TRAFFIC_SCRIPT" start "$KUBECONFIG" "$SEED" "${EXTRA_ARGS[@]}"

# 5. Déployer l'optimiseur
echo "" >&2
echo "=== [5/5] Déploiement de l'optimiseur ===" >&2
"$OPTIMIZER_SCRIPT" "$KUBECONFIG" "$SEED" "${EXTRA_ARGS[@]}"

# Attente de la durée du test
echo "" >&2
echo "=== Test en cours (${DURATION}s) — $(date '+%H:%M:%S') ===" >&2
sleep "$DURATION"
echo "=== Durée écoulée — $(date '+%H:%M:%S') ===" >&2

# Le trap EXIT se charge du cleanup

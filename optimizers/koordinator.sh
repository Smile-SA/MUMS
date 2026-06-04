#!/bin/bash
# Déploie Koordinator comme optimiseur de scheduling.
# Usage: ./koordinator.sh <kubeconfig> <seed>
# Les options inconnues sont ignorées.
#
# TODO: passer le nombre de replicas en option
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UTILS_DIR="$SCRIPT_DIR/../utils"

KUBECONFIG=$1
SEED=$2
# SEED non utilisé, conservé pour respecter la convention optimizer

"$UTILS_DIR/koordinator/deploy.sh" "$KUBECONFIG"

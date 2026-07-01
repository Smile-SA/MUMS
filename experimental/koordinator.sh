#!/bin/bash
# Deploys Koordinator as a scheduling optimizer.
# Usage: ./koordinator.sh <kubeconfig> <seed>
# Unknown options are ignored.
#
# TODO: expose replica count as an option
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UTILS_DIR="$SCRIPT_DIR/../utils"

KUBECONFIG=$1
SEED=$2
# SEED is unused; kept to match the optimizer module convention.

"$UTILS_DIR/koordinator/deploy.sh" "$KUBECONFIG"

#!/usr/bin/env bash
# no-disruption disruption module (contract 1): disrupts nothing.
# The cluster runs undisturbed for the whole run.
#
# Usage:
#   run.sh start <kubeconfig> <seed>

set -euo pipefail

usage() {
    echo "Usage: $0 start <kubeconfig> <seed>" >&2
    exit 1
}

ACTION="${1:-}"
if [ "$ACTION" != "start" ]; then
    [ -n "$ACTION" ] && echo "ERROR: unknown action '$ACTION'" >&2
    usage
fi
shift
[ "$#" -eq 2 ] || usage   # <kubeconfig> <seed>: unused

echo "=== no-disruption: the cluster is not disrupted ==="

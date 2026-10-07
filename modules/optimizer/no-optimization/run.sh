#!/usr/bin/env bash
# no-optimization optimizer module (contract 1): applies no optimization.
# Kubernetes default scheduling and controller behavior remain active.
#
# Usage:
#   run.sh start <kubeconfig>

set -euo pipefail

usage() {
    echo "Usage: $0 start <kubeconfig>" >&2
    exit 1
}

ACTION="${1:-}"
if [ "$ACTION" != "start" ]; then
    [ -n "$ACTION" ] && echo "ERROR: unknown action '$ACTION'" >&2
    usage
fi
shift
[ "$#" -eq 1 ] || usage   # <kubeconfig>: unused

echo "=== no-optimization: no additional optimization is applied ==="
echo "Kubernetes default scheduling and controller behavior remain active."

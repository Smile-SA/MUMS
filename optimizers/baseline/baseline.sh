#!/usr/bin/env bash
set -euo pipefail

# Minimal optimizer contract: deploy onto the cluster and stop there.
# Usage: ./baseline.sh deploy <kubeconfig>

ACTION="${1:-deploy}"

case "${ACTION}" in
  deploy)
    echo "=== Baseline optimizer: no additional optimization is applied ===" >&2
    echo "Kubernetes default scheduling and controller behavior remain active." >&2
    ;;
  -h|--help|help)
    cat <<USAGE
Usage: $0 deploy <kubeconfig>

Baseline optimizer adapter (minimal contract).
Deploys nothing: Kubernetes default scheduling remains active.
USAGE
    ;;
  *)
    echo "[ERROR] Unsupported baseline optimizer action: ${ACTION}" >&2
    exit 2
    ;;
esac

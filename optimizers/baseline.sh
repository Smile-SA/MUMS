#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-start}"

case "${ACTION}" in
  prepare|start|deploy)
    echo "=== Baseline optimizer: no additional optimization is applied ===" >&2
    echo "Kubernetes default scheduling and controller behavior remain active." >&2
    ;;
  stop|destroy)
    echo "=== Baseline optimizer: nothing to stop ===" >&2
    ;;
  status)
    echo "baseline"
    ;;
  collect)
    # No optimizer artifacts are produced by the baseline.
    ;;
  -h|--help|help)
    cat <<USAGE
Usage: $0 <prepare|start|deploy|stop|destroy|status|collect>

Baseline optimizer adapter.

This mode applies no additional optimization algorithm.
Kubernetes default scheduling remains active.
USAGE
    ;;
  *)
    echo "[ERROR] Unsupported baseline optimizer action: ${ACTION}" >&2
    exit 2
    ;;
esac

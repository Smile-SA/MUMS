#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ACTION="${1:-}"
shift || true

case "${ACTION}" in
  prepare)
    exec "${SCRIPT_DIR}/prepare.sh" "$@"
    ;;
  deploy|start)
    exec "${SCRIPT_DIR}/deploy.sh" "$@"
    ;;
  stop|destroy)
    # The current benchmark relies on whole-environment destruction for cleanup.
    # Keep this as a no-op adapter until stack-specific cleanup is required.
    echo "=== Online Boutique stack: no explicit ${ACTION} action required ===" >&2
    ;;
  status)
    echo "online-boutique"
    ;;
  help|-h|--help|"")
    cat <<USAGE
Usage: $0 <prepare|deploy|start|stop|destroy|status> ...

Current runner uses:
  $0 deploy <kubeconfig> <seed>
USAGE
    ;;
  *)
    echo "[ERROR] Unsupported Online Boutique stack action: ${ACTION}" >&2
    exit 2
    ;;
esac

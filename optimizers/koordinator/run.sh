#!/usr/bin/env bash
set -euo pipefail

# Minimal optimizer contract: deploy onto the cluster and stop there.
# It dies with the cluster on `environment destroy`; nothing to stop, no
# status to poll, no artifacts to collect (data collection is the
# observability module's job).
# Usage: ./run.sh deploy <kubeconfig>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd -P)"

ACTION="${1:-}"
shift || true

case "${ACTION}" in
  deploy)
    KUBECONFIG_PATH="${1:-}"
    if [ -z "${KUBECONFIG_PATH}" ]; then
      echo "Usage: $0 deploy <kubeconfig>" >&2
      exit 1
    fi
    exec "${REPO_ROOT}/utils/koordinator/deploy.sh" "${KUBECONFIG_PATH}"
    ;;
  -h|--help|help)
    echo "Usage: $0 deploy <kubeconfig>" >&2
    ;;
  *)
    echo "[ERROR] Unsupported Koordinator optimizer action: ${ACTION}" >&2
    exit 2
    ;;
esac

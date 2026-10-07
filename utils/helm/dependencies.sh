#!/usr/bin/env bash
# Helm 3: installed with the official installer script if missing.
# Usage: ./dependencies.sh install|check
set -euo pipefail

case "${1:-}" in
    install)
        if command -v helm >/dev/null 2>&1; then
            echo "=== Helm already installed: $(helm version --short) ==="
            exit 0
        fi
        echo "=== Installing Helm ==="
        curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
        ;;
    check) ;;  # `helm` on PATH is checked by the core
    *) echo "Usage: $0 install|check" >&2; exit 2 ;;
esac

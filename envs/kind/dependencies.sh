#!/usr/bin/env bash
# kind (Kubernetes in Docker) binary. Helm and the charts come from the declared
# utils; Docker is a prerequisite installed by hand.
# Usage: ./dependencies.sh install|check
set -euo pipefail

KIND_VERSION="latest"   # TODO: pin a release

case "${1:-}" in
    install)
        if command -v kind >/dev/null 2>&1; then
            echo "=== kind already installed: $(kind version) ==="
            exit 0
        fi
        case "$(uname -m)" in
            aarch64|arm64) arch=arm64 ;;
            *) arch=amd64 ;;
        esac
        echo "=== Installing kind (${KIND_VERSION}, ${arch}) ==="
        tmp="$(mktemp)"
        curl -fsSLo "$tmp" "https://kind.sigs.k8s.io/dl/${KIND_VERSION}/kind-linux-${arch}"
        chmod +x "$tmp"
        sudo mv "$tmp" /usr/local/bin/kind
        ;;
    check)
        # `docker` and `kind` on PATH are checked by the core: verify the Docker
        # daemon answers, so that a stopped daemon is caught before the run.
        docker info >/dev/null 2>&1 || { echo "Docker daemon not reachable (running? user in the docker group?)"; exit 1; }
        ;;
    *) echo "Usage: $0 install|check" >&2; exit 2 ;;
esac

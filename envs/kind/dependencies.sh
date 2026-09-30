#!/usr/bin/env bash
# kind (Kubernetes in Docker) binary. Helm and the charts come from the declared
# utils; Docker is a prerequisite installed by hand.
#
# The kind version is set in ./kind-version:
#   system   use the system's `kind` (on PATH), whatever its version; if missing,
#            install the latest release to /usr/local/bin.
#   vX.Y.Z   use a module-local binary (.bin/kind-vX.Y.Z), installed here: several
#            modules can then pin different kind versions side by side.
#
# Usage: ./dependencies.sh install|check
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
KIND_VERSION="$(tr -d '[:space:]' < "${SCRIPT_DIR}/kind-version")"
LOCAL_BIN="${SCRIPT_DIR}/.bin/kind-${KIND_VERSION}"

download_kind() {  # <version: latest|vX.Y.Z> <destination>  (latest = latest release)
    local arch
    case "$(uname -m)" in
        x86_64|amd64)  arch=amd64 ;;
        aarch64|arm64) arch=arm64 ;;
        *) echo "ERROR: unsupported architecture '$(uname -m)' (kind is published for amd64 and arm64)" >&2; exit 1 ;;
    esac
    local tmp; tmp="$(mktemp)"
    echo "=== Downloading kind ${1} (${arch}) ==="
    curl -fsSLo "$tmp" "https://kind.sigs.k8s.io/dl/${1}/kind-linux-${arch}"
    chmod +x "$tmp"
    mv "$tmp" "$2"
}

install() {
    if [ "$KIND_VERSION" = "system" ]; then
        if command -v kind >/dev/null 2>&1; then
            echo "=== kind already installed: $(kind version) ==="
            return 0
        fi
        local tmp; tmp="$(mktemp)"
        download_kind latest "$tmp"
        sudo mv "$tmp" /usr/local/bin/kind
    else
        if [ -x "$LOCAL_BIN" ]; then
            echo "=== kind ${KIND_VERSION} already installed: ${LOCAL_BIN} ==="
            return 0
        fi
        mkdir -p "$(dirname "$LOCAL_BIN")"
        download_kind "$KIND_VERSION" "$LOCAL_BIN"
    fi
}

check() {
    # The Docker daemon must answer (the `docker` command itself is checked by the core).
    docker info >/dev/null 2>&1 || { echo "Docker daemon not reachable (running? user in the docker group?)"; exit 1; }
    if [ "$KIND_VERSION" = "system" ]; then
        command -v kind >/dev/null 2>&1 || { echo "kind not found on PATH"; exit 1; }
    else
        [ -x "$LOCAL_BIN" ] || { echo "kind ${KIND_VERSION} not installed (${LOCAL_BIN})"; exit 1; }
    fi
}

case "${1:-}" in
    install) install ;;
    check) check ;;
    *) echo "Usage: $0 install|check" >&2; exit 2 ;;
esac

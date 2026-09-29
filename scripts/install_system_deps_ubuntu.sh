#!/usr/bin/env bash
# Global (core) system dependencies only: Python, jq, kubectl and base tools.
# Everything else is installed by the modules that need it
# (benchmark-platform deps install <module>).
set -euo pipefail

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "[ERROR] This installer is only intended for Linux." >&2
  exit 1
fi

if [[ ! -f /etc/os-release ]]; then
  echo "[ERROR] Cannot detect Linux distribution: /etc/os-release missing." >&2
  exit 1
fi

# shellcheck disable=SC1091
source /etc/os-release

case "${ID_LIKE:-${ID}}" in
  *debian*|*ubuntu*)
    ;;
  *)
    echo "[ERROR] This installer currently supports Ubuntu/Debian-like distributions only." >&2
    echo "Detected ID='${ID}', ID_LIKE='${ID_LIKE:-}'." >&2
    exit 1
    ;;
esac

ARCH=$(uname -m)
[[ "$ARCH" == "aarch64" ]] && ARCH="arm64" || ARCH="amd64"
KUBECTL_VERSION="${KUBECTL_VERSION:-stable}"

echo "=== Installing base packages ==="
sudo apt-get update
sudo apt-get install -y \
  ca-certificates \
  curl \
  gnupg \
  jq \
  lsb-release \
  python3 \
  python3-venv \
  python3-pip


echo
echo "=== Installing kubectl ==="
if [[ "${KUBECTL_VERSION}" == "stable" ]]; then
  KUBECTL_VERSION="$(curl -fsSL https://dl.k8s.io/release/stable.txt)"
fi

curl -fsSLo /tmp/kubectl \
  "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/${ARCH}/kubectl"
chmod +x /tmp/kubectl
sudo mv /tmp/kubectl /usr/local/bin/kubectl

echo
echo "=== Installed tool versions ==="
python3 --version
kubectl version --client=true || kubectl version --client || true
jq --version || true

echo
echo "System dependency installation complete."
echo
echo "Next steps:"
echo "  1. Run: make setup-dev"
echo "  2. Install the dependencies of the modules you use, e.g.:"
echo "       benchmark-platform deps install envs.kind"
echo "     (Docker, kind, Helm and the charts are installed by the modules that need them.)"

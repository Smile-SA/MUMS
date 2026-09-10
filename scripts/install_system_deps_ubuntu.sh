#!/usr/bin/env bash
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

ARCH="$(dpkg --print-architecture)"
KIND_VERSION="${KIND_VERSION:-latest}"
KUBECTL_VERSION="${KUBECTL_VERSION:-stable}"
INSTALL_DOCKER="${INSTALL_DOCKER:-true}"

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

if [[ "${INSTALL_DOCKER}" == "true" ]]; then
  echo
  echo "=== Installing Docker Engine from Docker apt repository ==="

  sudo install -m 0755 -d /etc/apt/keyrings

  if [[ ! -f /etc/apt/keyrings/docker.asc ]]; then
    curl -fsSL "https://download.docker.com/linux/${ID}/gpg" \
      | sudo tee /etc/apt/keyrings/docker.asc >/dev/null
    sudo chmod a+r /etc/apt/keyrings/docker.asc
  fi

  CODENAME="${VERSION_CODENAME:-$(lsb_release -cs)}"

  echo \
    "deb [arch=${ARCH} signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/${ID} ${CODENAME} stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null

  sudo apt-get update
  sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

  if ! groups "${USER}" | grep -q '\bdocker\b'; then
    echo
    echo "=== Adding current user to docker group ==="
    sudo usermod -aG docker "${USER}"
    echo "[WARN] You must log out and log back in, or run 'newgrp docker', before Docker works without sudo."
  fi
fi

echo
echo "=== Installing kubectl ==="
if [[ "${KUBECTL_VERSION}" == "stable" ]]; then
  KUBECTL_VERSION="$(curl -fsSL https://dl.k8s.io/release/stable.txt)"
fi

curl -fsSLo /tmp/kubectl \
  "https://dl.k8s.io/release/${KUBECTL_VERSION}/bin/linux/amd64/kubectl"
chmod +x /tmp/kubectl
sudo mv /tmp/kubectl /usr/local/bin/kubectl

echo
echo "=== Installing kind ==="
ARCH=$(uname -m)
[[ "$ARCH" == "aarch64" ]] && ARCH="arm64" || ARCH="amd64"
if [[ "${KIND_VERSION}" == "latest" ]]; then
  KIND_URL="https://kind.sigs.k8s.io/dl/latest/kind-linux-${ARCH}"
else
  KIND_URL="https://kind.sigs.k8s.io/dl/${KIND_VERSION}/kind-linux-${ARCH}"
fi

curl -fsSLo /tmp/kind "${KIND_URL}"
chmod +x /tmp/kind
sudo mv /tmp/kind /usr/local/bin/kind

echo
echo "=== Installing Helm ==="
curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

echo
echo "=== Installed tool versions ==="
python3 --version
docker --version || true
kubectl version --client=true || kubectl version --client || true
kind version || true
helm version --short || helm version || true
jq --version || true

echo
echo "System dependency installation complete."
echo
echo "Next steps:"
echo "  1. If Docker group membership changed, log out/in or run: newgrp docker"
echo "  2. Run: make setup-dev"
echo "  3. Run: make doctor"

#!/bin/bash
# Usage: ./deploy.sh <kubeconfig> <ip_range> [<ip_range> ...]
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UTILS_DIR="$SCRIPT_DIR/.."
KUBECONFIG=$1
shift

if [ -z "$KUBECONFIG" ] || [ "$#" -eq 0 ]; then
    echo "Usage: $0 <kubeconfig> <ip_range> [<ip_range> ...]" >&2
    exit 1
fi

echo "=== Installation MetalLB ===" >&2
"$UTILS_DIR/helm/install.sh" \
    "$KUBECONFIG" \
    metallb \
    metallb \
    --namespace metallb-system

ADDRESSES_YAML=""
for range in "$@"; do
    ADDRESSES_YAML="${ADDRESSES_YAML}  - ${range}
"
done

echo "=== Configuration IPAddressPool: $* ===" >&2
kubectl apply --kubeconfig "$KUBECONFIG" -f - <<EOF
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default-pool
  namespace: metallb-system
spec:
  addresses:
${ADDRESSES_YAML}---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: default-l2
  namespace: metallb-system
spec:
  ipAddressPools:
  - default-pool
EOF
echo "=== MetalLB prêt ($*) ===" >&2
#!/bin/bash
# Usage: ./deploy.sh <kubeconfig> <ip_range> [<ip_range> ...]
set -e
UTILS_DIR="${BENCHMARK_UTILS_PATH:?BENCHMARK_UTILS_PATH is not set}"

KUBECONFIG="${1:-}"
shift || true

if [ -z "$KUBECONFIG" ] || [ "$#" -eq 0 ]; then
    echo "Usage: $0 <kubeconfig> <ip_range> [<ip_range> ...]" >&2
    exit 1
fi

if [ ! -f "$KUBECONFIG" ]; then
    echo "ERROR: kubeconfig '$KUBECONFIG' not found" >&2
    exit 1
fi

ADDRESSES_YAML=""
for range in "$@"; do
    ADDRESSES_YAML="${ADDRESSES_YAML}  - ${range}
"
done

echo "=== Installation MetalLB ===" >&2
"$UTILS_DIR/helm/install.sh" \
  "$KUBECONFIG" \
  metallb \
  metallb \
  --namespace metallb-system

echo "=== Waiting for MetalLB components ===" >&2

kubectl --kubeconfig "${KUBECONFIG}" \
  -n metallb-system \
  rollout status deployment/metallb-controller \
  --timeout=180s

kubectl --kubeconfig "${KUBECONFIG}" \
  -n metallb-system \
  rollout status daemonset/metallb-speaker \
  --timeout=180s

echo "=== Configuration IPAddressPool: $* ===" >&2
kubectl apply --kubeconfig "$KUBECONFIG" -f - <<EOF2
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
EOF2

echo "=== MetalLB ready — address ranges: $* ===" >&2

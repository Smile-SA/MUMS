#!/bin/bash
# Usage: ./deploy.sh <kubeconfig> <ip_range>
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
UTILS_DIR="$SCRIPT_DIR/.."

KUBECONFIG=$1
IP_RANGE=$2

if [ -z "$KUBECONFIG" ] || [ -z "$IP_RANGE" ]; then
    echo "Usage: $0 <kubeconfig> <ip_range>" >&2
    exit 1
fi

# Calcul du nombre d'IPs disponibles
START_IP=$(echo "$IP_RANGE" | cut -d'-' -f1)
END_IP=$(echo "$IP_RANGE" | cut -d'-' -f2)
START_INT=$(echo "$START_IP" | awk -F. '{print ($1*256^3)+($2*256^2)+($3*256)+$4}')
END_INT=$(echo "$END_IP" | awk -F. '{print ($1*256^3)+($2*256^2)+($3*256)+$4}')
IP_COUNT=$(( END_INT - START_INT + 1 ))

echo "=== Installation MetalLB ===" >&2
"$UTILS_DIR/helm/install.sh" \
  "$KUBECONFIG" \
  metallb \
  metallb \
  --namespace metallb-system

echo "=== Configuration IPAddressPool: $IP_RANGE ($IP_COUNT IPs available) ===" >&2

echo "=== Waiting for MetalLB components ===" >&2

kubectl --kubeconfig "${KUBECONFIG_PATH}" \
  -n metallb-system \
  rollout status deployment/metallb-controller \
  --timeout=180s

kubectl --kubeconfig "${KUBECONFIG_PATH}" \
  -n metallb-system \
  rollout status daemonset/metallb-speaker \
  --timeout=180s

kubectl apply --kubeconfig "$KUBECONFIG" -f - <<EOF
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default-pool
  namespace: metallb-system
spec:
  addresses:
    - $IP_RANGE
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: default-l2
  namespace: metallb-system
spec:
  ipAddressPools:
  - default-pool
EOF

echo "=== MetalLB ready — $IP_COUNT IPs available ($IP_RANGE) ===" >&2

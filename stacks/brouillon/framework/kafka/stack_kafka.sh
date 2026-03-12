#!/bin/bash
# Usage: ./stack_kafka.sh <KUBECONFIG> <SEED>

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <KUBECONFIG> <SEED>"
    exit 1
fi

KUBECONFIG=$1
SEED=$2

source "$(dirname "$0")/../../utils/base_helm_stack.sh"

deploy_helm_stack "$KUBECONFIG" "$SEED" \
    "bitnami/kafka" \
    "bitnami" \
    "https://charts.bitnami.com/bitnami"

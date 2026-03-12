#!/bin/bash
# Usage: ./stack_spark.sh <KUBECONFIG> <SEED>

if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <KUBECONFIG> <SEED>"
    exit 1
fi

KUBECONFIG=$1
SEED=$2

source "$(dirname "$0")/../../utils/base_helm_stack.sh"

deploy_helm_stack "$KUBECONFIG" "$SEED" \
    "spark-operator/spark-operator" \
    "spark-operator" \
    "https://googlecloudplatform.github.io/spark-on-k8s-operator"

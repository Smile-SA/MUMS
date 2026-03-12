#!/bin/bash
# Télécharge le chart Helm de Prometheus.
# Usage: ./prepare.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

"$SCRIPT_DIR/../helm/prepare.sh" \
    prometheus-community \
    https://prometheus-community.github.io/helm-charts \
    prometheus-community/prometheus \
    28.13.0

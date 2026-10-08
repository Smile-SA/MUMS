#!/bin/bash
# Deploys Prometheus on a Kubernetes cluster via Helm, set up to keep measuring
# when the cluster is overloaded.
# Usage: ./deploy.sh <kubeconfig> <chart_version> <scrape_interval_seconds> <placement>
#   chart_version: version of the prometheus-community/prometheus chart (already
#     fetched into utils/helm/chart-repository/).
#   scrape_interval_seconds: how often Prometheus collects its targets (set to the
#     module's scrape frequency, so that each of our scrapes brings new samples).
#   placement: control-plane (Prometheus and kube-state-metrics run on the
#     control-plane node, away from the measured workload) or any.
set -euo pipefail

UTILS_DIR="${BENCHMARK_UTILS_PATH:?BENCHMARK_UTILS_PATH is not set}"

KUBECONFIG="${1:-}"
CHART_VERSION="${2:-}"
INTERVAL="${3:-}"
PLACEMENT="${4:-}"
PRIORITY_CLASS="benchmark-observability"

if [ -z "$KUBECONFIG" ] || [ -z "$CHART_VERSION" ] || [ -z "$INTERVAL" ] || [ -z "$PLACEMENT" ]; then
    echo "Usage: $0 <kubeconfig> <chart_version> <scrape_interval_seconds> <control-plane|any>" >&2
    exit 1
fi

if [ ! -f "$KUBECONFIG" ]; then
    echo "ERROR: kubeconfig '$KUBECONFIG' not found" >&2
    exit 1
fi

# Prometheus waits for a target as long as the interval allows: fewer samples
# lost when the cluster is overloaded (scrape_timeout must not exceed the interval).
TIMEOUT=$INTERVAL

# High priority: the measurement must be the last thing to go when the cluster
# is under pressure (never evicted or preempted before the workload).
kubectl --kubeconfig "$KUBECONFIG" apply -f - >/dev/null <<EOF2
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: ${PRIORITY_CLASS}
value: 1000000
globalDefault: false
description: "Benchmark platform observability (Prometheus): kept running under pressure."
EOF2

PLACEMENT_ARGS=()
case "$PLACEMENT" in
    control-plane)
        for component in server kube-state-metrics; do
            PLACEMENT_ARGS+=(
                --set-json "${component}.nodeSelector={\"node-role.kubernetes.io/control-plane\":\"\"}"
                --set-json "${component}.tolerations=[{\"key\":\"node-role.kubernetes.io/control-plane\",\"operator\":\"Exists\",\"effect\":\"NoSchedule\"}]"
            )
        done
        ;;
    any) ;;
    *)
        echo "ERROR: placement must be control-plane or any (got '$PLACEMENT')" >&2
        exit 1
        ;;
esac

"$UTILS_DIR/helm/install.sh" \
    "$KUBECONFIG" \
    prometheus \
    prometheus \
    "$CHART_VERSION" \
    --namespace monitoring \
    --set "server.global.scrape_interval=${INTERVAL}s" \
    --set "server.global.scrape_timeout=${TIMEOUT}s" \
    --set "server.priorityClassName=${PRIORITY_CLASS}" \
    --set "kube-state-metrics.priorityClassName=${PRIORITY_CLASS}" \
    --set "prometheus-node-exporter.priorityClassName=${PRIORITY_CLASS}" \
    --set "server.resources.requests.cpu=500m" \
    --set "server.resources.requests.memory=1Gi" \
    --set "server.resources.limits.cpu=500m" \
    --set "server.resources.limits.memory=1Gi" \
    --set "alertmanager.enabled=false" \
    --set "prometheus-pushgateway.enabled=false" \
    "${PLACEMENT_ARGS[@]}"

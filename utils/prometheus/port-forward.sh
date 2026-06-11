#!/bin/bash
# Starts a port-forward to Prometheus and writes the PID to a file.
# Usage: ./port-forward.sh <kubeconfig> <name>

KUBECONFIG=$1
NAME=$2

PROMETHEUS_LOCAL_PORT="${PROMETHEUS_LOCAL_PORT:-9090}"
PROMETHEUS_SERVICE_PORT="${PROMETHEUS_SERVICE_PORT:-80}"

if [ -z "$KUBECONFIG" ] || [ -z "$NAME" ]; then
    echo "Usage: $0 <kubeconfig> <name>" >&2
    exit 1
fi

if [ ! -f "$KUBECONFIG" ]; then
    echo "ERROR: kubeconfig '$KUBECONFIG' not found" >&2
    exit 1
fi

PID_FILE="/tmp/prometheus-pf-${NAME}.pid"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Port-forward already running (PID $(cat "$PID_FILE"))" >&2
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"${SCRIPT_DIR}/check_local_port.sh" "${PROMETHEUS_LOCAL_PORT}" >&2

kubectl --kubeconfig "$KUBECONFIG" \
    port-forward -n monitoring svc/prometheus-server \
    "${PROMETHEUS_LOCAL_PORT}:${PROMETHEUS_SERVICE_PORT}" \
    > /dev/null 2>&1 &
PF_PID=$!
echo $PF_PID > "$PID_FILE"

echo "=== Waiting for Prometheus port-forward..." >&2
for i in $(seq 1 15); do
    if curl -s http://localhost:9090/-/healthy > /dev/null 2>&1; then
        echo "=== Prometheus available at http://localhost:9090 (PID $PF_PID)" >&2
        exit 0
    fi
    sleep 1
done

echo "ERROR: Prometheus port-forward failed to start" >&2
kill "$PF_PID" 2>/dev/null
rm "$PID_FILE"
exit 1
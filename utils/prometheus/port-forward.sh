#!/usr/bin/env bash
# Starts a port-forward to Prometheus in the background and writes its PID.
# Usage: ./port-forward.sh <kubeconfig> <local_port> <pid_file> <log_file> [<service_port>]
#   service_port: port of svc/prometheus-server in the cluster (default: 80)

set -euo pipefail

if [ "$#" -lt 4 ]; then
    echo "Usage: $0 <kubeconfig> <local_port> <pid_file> <log_file> [<service_port>]" >&2
    exit 1
fi

KUBECONFIG_PATH="$1"
LOCAL_PORT="$2"
PID_FILE="$3"
LOG_FILE="$4"
SERVICE_PORT="${5:-80}"

if [ ! -f "$KUBECONFIG_PATH" ]; then
    echo "ERROR: kubeconfig '$KUBECONFIG_PATH' not found" >&2
    exit 1
fi

mkdir -p "$(dirname "$PID_FILE")" "$(dirname "$LOG_FILE")"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Port-forward already running (PID $(cat "$PID_FILE"))" >&2
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
"${SCRIPT_DIR}/check_local_port.sh" "${LOCAL_PORT}" >&2

kubectl --kubeconfig "$KUBECONFIG_PATH" \
    port-forward -n monitoring svc/prometheus-server \
    "${LOCAL_PORT}:${SERVICE_PORT}" \
    > "$LOG_FILE" 2>&1 &
PF_PID=$!
echo "$PF_PID" > "$PID_FILE"

echo "=== Waiting for Prometheus port-forward..." >&2
for _ in $(seq 1 15); do
    if curl -fsS "http://127.0.0.1:${LOCAL_PORT}/-/healthy" > /dev/null 2>&1; then
        echo "=== Prometheus available at http://127.0.0.1:${LOCAL_PORT} (PID $PF_PID)" >&2
        exit 0
    fi
    sleep 1
done

echo "ERROR: Prometheus port-forward failed to start" >&2
echo "--- port-forward log: ${LOG_FILE} ---" >&2
cat "$LOG_FILE" >&2 || true
kill "$PF_PID" 2>/dev/null || true
rm -f "$PID_FILE"
exit 1

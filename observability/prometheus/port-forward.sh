#!/usr/bin/env bash
# Starts a port-forward to Prometheus in the background, restarted automatically
# whenever it drops (e.g. the Prometheus pod restarts), and writes the PID of its
# supervising loop.
# Usage: ./port-forward.sh <kubeconfig> <local_port> <pid_file> <log_file> <events_file> [<service_port>]
#   events_file: CSV journal of the port-forward's starts and drops (timestamp, event, detail).
#   service_port: port of svc/prometheus-server in the cluster (default: 80).

set -euo pipefail

if [ "$#" -lt 5 ]; then
    echo "Usage: $0 <kubeconfig> <local_port> <pid_file> <log_file> <events_file> [<service_port>]" >&2
    exit 1
fi

KUBECONFIG_PATH="$1"
LOCAL_PORT="$2"
PID_FILE="$3"
LOG_FILE="$4"
EVENTS_FILE="$5"
SERVICE_PORT="${6:-80}"
RESTART_DELAY_SECONDS=2

if [ ! -f "$KUBECONFIG_PATH" ]; then
    echo "ERROR: kubeconfig '$KUBECONFIG_PATH' not found" >&2
    exit 1
fi

mkdir -p "$(dirname "$PID_FILE")" "$(dirname "$LOG_FILE")" "$(dirname "$EVENTS_FILE")"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "Port-forward already running (PID $(cat "$PID_FILE"))" >&2
    exit 0
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
"${SCRIPT_DIR}/check_local_port.sh" "${LOCAL_PORT}" >&2

[ -s "$EVENTS_FILE" ] || echo "timestamp,event,detail" > "$EVENTS_FILE"

# Supervising loop: runs the port-forward, and starts it again when it exits.
(
    child=""
    trap '[ -n "$child" ] && kill "$child" 2>/dev/null; exit 0' TERM INT
    while true; do
        echo "$(date -u +%Y-%m-%dT%H:%M:%SZ),started," >> "$EVENTS_FILE"
        kubectl --kubeconfig "$KUBECONFIG_PATH" \
            port-forward -n monitoring svc/prometheus-server \
            "${LOCAL_PORT}:${SERVICE_PORT}" >> "$LOG_FILE" 2>&1 &
        child=$!
        rc=0
        wait "$child" || rc=$?
        echo "$(date -u +%Y-%m-%dT%H:%M:%SZ),dropped,exit code ${rc}" >> "$EVENTS_FILE"
        child=""
        sleep "$RESTART_DELAY_SECONDS" & wait $!   # interruptible by the TERM trap
    done
) &
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

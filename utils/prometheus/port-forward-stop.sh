#!/bin/bash
# Stops the Prometheus port-forward for a given name.
# Usage: ./port-forward-stop.sh <name>

NAME=$1

if [ -z "$NAME" ]; then
    echo "Usage: $0 <name>" >&2
    exit 1
fi

BENCHMARK_PID_DIR="${BENCHMARK_PID_DIR:-/tmp}"
mkdir -p "${BENCHMARK_PID_DIR}"
BENCHMARK_PID_DIR="$(cd "${BENCHMARK_PID_DIR}" && pwd -P)"

PID_FILE="${BENCHMARK_PID_DIR}/prometheus-pf-${NAME}.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    kill "$PID" 2>/dev/null && echo "=== Port-forward stopped (PID $PID)" >&2
    rm "$PID_FILE"
else
    echo "No port-forward found for '$NAME'" >&2
fi
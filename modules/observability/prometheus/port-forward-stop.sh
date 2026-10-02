#!/usr/bin/env bash
# Stops the Prometheus port-forward started by port-forward.sh (its supervising
# loop and the current kubectl port-forward).
# Usage: ./port-forward-stop.sh <pid_file>
# Succeeds if nothing is running (dirty states are expected).

set -euo pipefail

if [ "$#" -ne 1 ]; then
    echo "Usage: $0 <pid_file>" >&2
    exit 1
fi

PID_FILE="$1"

if [ -f "$PID_FILE" ]; then
    PID="$(cat "$PID_FILE")"
    # The supervising loop stops its current port-forward on TERM; also stop
    # its children directly, in case the loop is already gone.
    pkill -TERM -P "$PID" 2>/dev/null || true
    if kill "$PID" 2>/dev/null; then
        echo "=== Port-forward stopped (PID $PID)" >&2
    else
        echo "WARNING: port-forward $PID already stopped" >&2
    fi
    rm -f "$PID_FILE"
else
    echo "No port-forward PID file: $PID_FILE" >&2
fi

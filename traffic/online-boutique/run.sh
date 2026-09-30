#!/usr/bin/env bash
# Online Boutique traffic module (contract 1): Locust load from the host machine.
#
# Usage:
#   run.sh start <kubeconfig> <seed> <data_dir> --log_dir <dir> --extras_dir <dir>
#                [--shape <name>] [--cycle_minutes N]
#   run.sh stop  <kubeconfig> --log_dir <dir> --extras_dir <dir> [...]
#
# Data: none yet (standard traffic format to define). Locust CSV files are not
# a standard format: they go to <extras_dir> (locust_*.csv).
# Logs: <log_dir>/locust.log. Internal state: <extras_dir>/locust.pid.
# Shapes: shapes/<shape>.py in this module.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
NAMESPACE="online-boutique"

usage() {
    echo "Usage:" >&2
    echo "  $0 start <kubeconfig> <seed> <data_dir> --log_dir <dir> --extras_dir <dir> [--shape <name>] [--cycle_minutes N]" >&2
    echo "  $0 stop  <kubeconfig> --log_dir <dir> --extras_dir <dir>" >&2
    exit 1
}

ACTION="${1:-}"
[ -n "$ACTION" ] || usage
shift

case "$ACTION" in
    start)
        [ "$#" -ge 3 ] || usage
        KUBECONFIG_PATH="$1"; SEED="$2"; DATA_DIR="$3"   # unused until the traffic format exists
        shift 3
        ;;
    stop)
        [ "$#" -ge 1 ] || usage
        KUBECONFIG_PATH="$1"
        shift
        ;;
    *)
        echo "ERROR: unknown action '$ACTION'" >&2
        usage
        ;;
esac

LOG_DIR=""
EXTRAS_DIR=""
SHAPE="day_profile"
CYCLE_MINUTES=60

while [ "$#" -gt 0 ]; do
    case "$1" in
        --log_dir)       LOG_DIR="$2";       shift 2 ;;
        --extras_dir)    EXTRAS_DIR="$2";    shift 2 ;;
        --shape)         SHAPE="$2";         shift 2 ;;
        --cycle_minutes) CYCLE_MINUTES="$2"; shift 2 ;;
        *)
            echo "ERROR: unknown option '$1'" >&2
            usage
            ;;
    esac
done

if [ -z "$LOG_DIR" ] || [ -z "$EXTRAS_DIR" ]; then
    echo "ERROR: --log_dir and --extras_dir are required" >&2
    exit 1
fi
mkdir -p "$LOG_DIR" "$EXTRAS_DIR"
# Absolute paths: Locust is started from the module directory.
LOG_DIR="$(cd "$LOG_DIR" && pwd -P)"
EXTRAS_DIR="$(cd "$EXTRAS_DIR" && pwd -P)"

PID_FILE="${EXTRAS_DIR}/locust.pid"

case "$ACTION" in
    start)
        if [ ! -f "$KUBECONFIG_PATH" ]; then
            echo "ERROR: kubeconfig '$KUBECONFIG_PATH' not found" >&2
            exit 1
        fi

        if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
            echo "ERROR: traffic already running (PID $(cat "$PID_FILE"))" >&2
            exit 1
        fi
        rm -f "$PID_FILE"

        SHAPE_FILE="${SCRIPT_DIR}/shapes/${SHAPE}.py"
        if [ ! -f "$SHAPE_FILE" ]; then
            echo "ERROR: shape '$SHAPE' not found ($SHAPE_FILE)" >&2
            exit 1
        fi

        KUBECONFIG_PATH="$(cd "$(dirname "$KUBECONFIG_PATH")" && pwd -P)/$(basename "$KUBECONFIG_PATH")"
        LOG_FILE="${LOG_DIR}/locust.log"
        CSV_PREFIX="${EXTRAS_DIR}/locust"

        TARGET="$("${SCRIPT_DIR}/check_frontend.sh" "$KUBECONFIG_PATH" "$NAMESPACE")"

        echo "=== Online Boutique traffic ==="
        echo "    Target : $TARGET"
        echo "    Shape  : $SHAPE"
        echo "    Seed   : $SEED"
        echo "    Cycle  : ${CYCLE_MINUTES} minutes"

        cd "$SCRIPT_DIR"
        locust \
            -f "${SCRIPT_DIR}/locustfile.py,${SHAPE_FILE}" \
            --host "$TARGET" \
            --headless \
            --seed "$SEED" \
            --duration-minutes "$CYCLE_MINUTES" \
            --csv "$CSV_PREFIX" \
            --csv-full-history \
            > "$LOG_FILE" 2>&1 &
        LOCUST_PID=$!
        echo "$LOCUST_PID" > "$PID_FILE"

        # Fail loudly if Locust dies right away (missing package, bad shape...),
        # instead of running a benchmark without traffic.
        sleep 3
        if ! kill -0 "$LOCUST_PID" 2>/dev/null; then
            echo "ERROR: Locust exited right after start. Log: ${LOG_FILE}" >&2
            cat "$LOG_FILE" >&2 || true
            rm -f "$PID_FILE"
            exit 1
        fi

        echo "=== Traffic started (PID ${LOCUST_PID}, log: ${LOG_FILE}, csv: ${CSV_PREFIX}_*.csv)"
        ;;

    stop)
        # Must succeed whatever is running (start may have failed half-way).
        if [ ! -f "$PID_FILE" ]; then
            echo "No Locust PID file: $PID_FILE" >&2
            exit 0
        fi

        PID="$(cat "$PID_FILE")"
        if kill "$PID" 2>/dev/null; then
            # Give Locust time to flush its CSV files.
            for _ in $(seq 1 20); do
                kill -0 "$PID" 2>/dev/null || break
                sleep 0.5
            done
            kill -9 "$PID" 2>/dev/null || true
            echo "=== Traffic stopped (PID $PID)"
        else
            echo "WARNING: Locust $PID already stopped" >&2
        fi
        rm -f "$PID_FILE"
        ;;
esac

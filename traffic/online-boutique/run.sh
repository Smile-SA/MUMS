#!/bin/bash
# Generates traffic against Online Boutique from the host machine.
# Usage:
#   ./run.sh start <kubeconfig> <seed> [--shape=<name>] [--duration=<minutes>] [options ...]
#   ./run.sh stop  <kubeconfig>
#
# Options (start):
#   --shape=<name>      Traffic shape to use (default: day_profile)
#   --duration=<min>    Cycle duration in minutes (overrides DURATION_MINUTES from the shape)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
TRAFFIC_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

ACTION=$1
shift

case "$ACTION" in

    start)
        KUBECONFIG=$1
        SEED=$2
        shift 2

        if [ -z "$KUBECONFIG" ] || [ -z "$SEED" ]; then
            echo "Usage: $0 start <kubeconfig> <seed> [--shape=<name>] [--duration=<minutes>]" >&2
            exit 1
        fi

        if [ ! -f "$KUBECONFIG" ]; then
            echo "ERROR: kubeconfig '$KUBECONFIG' not found" >&2
            exit 1
        fi

        BENCHMARK_LOG_DIR="${BENCHMARK_LOG_DIR:-/tmp}"
        BENCHMARK_PID_DIR="${BENCHMARK_PID_DIR:-/tmp}"
        BENCHMARK_TRAFFIC_DIR="${BENCHMARK_TRAFFIC_DIR:-${BENCHMARK_LOG_DIR}}"

        mkdir -p "${BENCHMARK_LOG_DIR}" "${BENCHMARK_PID_DIR}" "${BENCHMARK_TRAFFIC_DIR}"

        # Convert to absolute paths before `cd "$TRAFFIC_DIR"`.
        BENCHMARK_LOG_DIR="$(cd "${BENCHMARK_LOG_DIR}" && pwd -P)"
        BENCHMARK_PID_DIR="$(cd "${BENCHMARK_PID_DIR}" && pwd -P)"
        BENCHMARK_TRAFFIC_DIR="$(cd "${BENCHMARK_TRAFFIC_DIR}" && pwd -P)"

        RUN_NAME="$(basename "$KUBECONFIG")"
        PID_FILE="${BENCHMARK_PID_DIR}/traffic-${RUN_NAME}.pid"
        LOG_FILE="${BENCHMARK_LOG_DIR}/traffic.log"
        LOCUST_CSV_PREFIX="${BENCHMARK_TRAFFIC_DIR}/locust"

        if [ -f "$PID_FILE" ]; then
            OLD_PID="$(cat "$PID_FILE")"

            if kill -0 "$OLD_PID" 2>/dev/null; then
                echo "ERROR: traffic already running (PID $OLD_PID)" >&2
                exit 1
            fi

            echo "WARNING: stale traffic PID file removed (PID $OLD_PID)" >&2
            rm -f "$PID_FILE"
        fi

        SHAPE="day_profile"
        DURATION=""

        for arg in "$@"; do
            case $arg in
                --shape=*)    SHAPE="${arg#--shape=}" ;;
                --duration=*) DURATION="${arg#--duration=}" ;;
                *)  ;;
            esac
        done

        SHAPE_FILE="$TRAFFIC_DIR/shapes/${SHAPE}.py"
        if [ ! -f "$SHAPE_FILE" ]; then
            echo "ERROR: shape '$SHAPE' not found ($SHAPE_FILE)" >&2
            exit 1
        fi

        FRONTEND_URL="$(
            "${REPO_ROOT}/stacks/online-boutique/check_frontend.sh" "${KUBECONFIG}"
        )"
        echo "=== Locust target verified: ${FRONTEND_URL} ===" >&2

        TARGET="${FRONTEND_URL}"
        echo "=== Online Boutique traffic ===" >&2
        echo "    Target  : $TARGET" >&2
        echo "    Shape   : $SHAPE" >&2
        echo "    Seed    : $SEED" >&2
        [ -n "$DURATION" ] && echo "    Cycle   : ${DURATION} minutes" >&2

        [ -n "$DURATION" ] && export DURATION_MINUTES="$DURATION"

        cd "$TRAFFIC_DIR"
        locust \
            -f "$SCRIPT_DIR/locustfile.py,$SHAPE_FILE" \
            --host "$TARGET" \
            --headless \
            --seed "$SEED" \
            --csv "${LOCUST_CSV_PREFIX}" \
            --csv-full-history \
            > "$LOG_FILE" 2>&1 &

        echo $! > "$PID_FILE"
        echo "=== Traffic started (PID $(cat "$PID_FILE"), log: $LOG_FILE, csv: ${LOCUST_CSV_PREFIX}_*.csv)" >&2
        ;;

    stop)
        KUBECONFIG=$1
        if [ -z "$KUBECONFIG" ]; then
            echo "Usage: $0 stop <kubeconfig>" >&2
            exit 1
        fi

        BENCHMARK_PID_DIR="${BENCHMARK_PID_DIR:-/tmp}"
        mkdir -p "${BENCHMARK_PID_DIR}"
        BENCHMARK_PID_DIR="$(cd "${BENCHMARK_PID_DIR}" && pwd -P)"

        RUN_NAME="$(basename "$KUBECONFIG")"
        PID_FILE="${BENCHMARK_PID_DIR}/traffic-${RUN_NAME}.pid"
        if [ ! -f "$PID_FILE" ]; then
            echo "WARNING: no PID file found ($PID_FILE)" >&2
            exit 0
        fi

        PID=$(cat "$PID_FILE")
        if kill "$PID" 2>/dev/null; then
            echo "=== Traffic stopped (PID $PID)" >&2
        else
            echo "WARNING: process $PID already stopped" >&2
        fi
        rm -f "$PID_FILE"
        ;;

    *)
        echo "Usage: $0 <start|stop> ..." >&2
        echo "  start <kubeconfig> <seed> [--shape=<name>] [--duration=<minutes>]" >&2
        echo "  stop  <kubeconfig>" >&2
        exit 1
        ;;
esac

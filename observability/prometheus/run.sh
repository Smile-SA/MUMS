#!/usr/bin/env bash
# Prometheus observability module (contract 1): port-forward + scraper.
#
# Usage:
#   run.sh start <kubeconfig> <output_dir> --log_dir <dir> --extras_dir <dir>
#                [--frequency_seconds N] [--local_port N] [--timeout_seconds N]
#   run.sh stop  <kubeconfig> --log_dir <dir> --extras_dir <dir> [...]
#
# Contractual output: <output_dir>/metrics.om (OpenMetrics), plus
# <output_dir>/scrapes.csv (scrape metadata).
# Logs: <log_dir>/scraper.log, <log_dir>/port-forward.log.
# Internal state: PID files in <extras_dir>.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
UTILS_DIR="${BENCHMARK_UTILS_PATH:?BENCHMARK_UTILS_PATH is not set}"
SCRAPER="${UTILS_DIR}/scraper/scraper.py"

usage() {
    echo "Usage:" >&2
    echo "  $0 start <kubeconfig> <output_dir> --log_dir <dir> --extras_dir <dir> [--frequency_seconds N] [--local_port N] [--timeout_seconds N]" >&2
    echo "  $0 stop  <kubeconfig> --log_dir <dir> --extras_dir <dir>" >&2
    exit 1
}

ACTION="${1:-}"
[ -n "$ACTION" ] || usage
shift

case "$ACTION" in
    start)
        [ "$#" -ge 2 ] || usage
        KUBECONFIG_PATH="$1"; OUTPUT_DIR="$2"
        shift 2
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
FREQUENCY=15
LOCAL_PORT=9090
TIMEOUT=10

while [ "$#" -gt 0 ]; do
    case "$1" in
        --log_dir)           LOG_DIR="$2";    shift 2 ;;
        --extras_dir)        EXTRAS_DIR="$2"; shift 2 ;;
        --frequency_seconds) FREQUENCY="$2";  shift 2 ;;
        --local_port)        LOCAL_PORT="$2"; shift 2 ;;
        --timeout_seconds)   TIMEOUT="$2";    shift 2 ;;
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

SCRAPER_PID_FILE="${EXTRAS_DIR}/scraper.pid"
PF_PID_FILE="${EXTRAS_DIR}/port-forward.pid"

case "$ACTION" in
    start)
        if [ ! -f "$KUBECONFIG_PATH" ]; then
            echo "ERROR: kubeconfig '$KUBECONFIG_PATH' not found" >&2
            exit 1
        fi
        mkdir -p "$OUTPUT_DIR"

        OUTPUT_FILE="${OUTPUT_DIR}/metrics.om"
        SCRAPE_METADATA_FILE="${OUTPUT_DIR}/scrapes.csv"
        SCRAPER_LOG_FILE="${LOG_DIR}/scraper.log"
        BASE_URL="http://127.0.0.1:${LOCAL_PORT}"

        "${UTILS_DIR}/prometheus/port-forward.sh" \
            "$KUBECONFIG_PATH" "$LOCAL_PORT" "$PF_PID_FILE" "${LOG_DIR}/port-forward.log"

        python3 "$SCRAPER" \
            --url "$BASE_URL" \
            --output "$OUTPUT_FILE" \
            --metadata-output "$SCRAPE_METADATA_FILE" \
            --frequency "$FREQUENCY" \
            --timeout "$TIMEOUT" \
            > /dev/null \
            2> "$SCRAPER_LOG_FILE" &
        SCRAPER_PID=$!
        echo "$SCRAPER_PID" > "$SCRAPER_PID_FILE"

        # Fail loudly if the scraper dies right away, instead of running a
        # benchmark without metrics.
        sleep 2
        if ! kill -0 "$SCRAPER_PID" 2>/dev/null; then
            echo "ERROR: scraper exited right after start. Log: ${SCRAPER_LOG_FILE}" >&2
            cat "$SCRAPER_LOG_FILE" >&2 || true
            rm -f "$SCRAPER_PID_FILE"
            "${UTILS_DIR}/prometheus/port-forward-stop.sh" "$PF_PID_FILE"
            exit 1
        fi

        echo "=== Scraper started (PID ${SCRAPER_PID}, output: ${OUTPUT_FILE}, metadata: ${SCRAPE_METADATA_FILE}, log: ${SCRAPER_LOG_FILE}, source: ${BASE_URL})"
        ;;

    stop)
        # Must succeed whatever is running: scraper and port-forward may be
        # absent if start failed half-way.
        if [ -f "$SCRAPER_PID_FILE" ]; then
            PID="$(cat "$SCRAPER_PID_FILE")"
            if kill "$PID" 2>/dev/null; then
                echo "=== Scraper stopped (PID $PID)"
            else
                echo "WARNING: scraper $PID already stopped" >&2
            fi
            rm -f "$SCRAPER_PID_FILE"
        else
            echo "No scraper PID file: $SCRAPER_PID_FILE" >&2
        fi

        "${UTILS_DIR}/prometheus/port-forward-stop.sh" "$PF_PID_FILE"
        ;;
esac

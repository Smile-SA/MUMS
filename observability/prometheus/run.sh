#!/usr/bin/env bash
# Prometheus observability module (contract 1): port-forward + scraper.
#
# Usage:
#   run.sh start <kubeconfig> <data_dir> --log_dir <dir> --extras_dir <dir>
#                [--install_prometheus true|false] [--frequency_seconds N]
#                [--local_port N] [--timeout_seconds N]
#   run.sh stop  <kubeconfig> --log_dir <dir> --extras_dir <dir> [...]
#
# Data: <data_dir>/openmetrics/<index>.om, one OpenMetrics file per scrape
# (read them in order with: cat <data_dir>/openmetrics/*.om).
# Extras: scrapes.csv (journal of every scrape attempt, for debugging).
# Logs: <log_dir>/scraper.log, <log_dir>/port-forward.log.
# Internal state: PID files in <extras_dir>.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SCRAPER="${SCRIPT_DIR}/scraper.py"

usage() {
    echo "Usage:" >&2
    echo "  $0 start <kubeconfig> <data_dir> --log_dir <dir> --extras_dir <dir> [--frequency_seconds N] [--local_port N] [--timeout_seconds N]" >&2
    echo "  $0 stop  <kubeconfig> --log_dir <dir> --extras_dir <dir>" >&2
    exit 1
}

ACTION="${1:-}"
[ -n "$ACTION" ] || usage
shift

case "$ACTION" in
    start)
        [ "$#" -ge 2 ] || usage
        KUBECONFIG_PATH="$1"; DATA_DIR="$2"
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
INSTALL_PROMETHEUS=true
FREQUENCY=15
LOCAL_PORT=9090
TIMEOUT=10

while [ "$#" -gt 0 ]; do
    case "$1" in
        --log_dir)           LOG_DIR="$2";    shift 2 ;;
        --extras_dir)        EXTRAS_DIR="$2"; shift 2 ;;
        --install_prometheus) INSTALL_PROMETHEUS="$2"; shift 2 ;;
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
        mkdir -p "$DATA_DIR"

        METRICS_DIR="${DATA_DIR}/openmetrics"        # standard format: one OpenMetrics file per scrape
        SCRAPE_JOURNAL="${EXTRAS_DIR}/scrapes.csv"   # debug: every scrape attempt
        SCRAPER_LOG_FILE="${LOG_DIR}/scraper.log"
        BASE_URL="http://127.0.0.1:${LOCAL_PORT}"

        # Prometheus is installed by this module, unless the cluster already
        # provides one (install_prometheus: false), e.g. on a managed cloud cluster.
        if [ "$INSTALL_PROMETHEUS" = "true" ]; then
            "${SCRIPT_DIR}/deploy.sh" "$KUBECONFIG_PATH"
        else
            echo "=== Prometheus not installed by the module (install_prometheus: false) ==="
        fi

        "${SCRIPT_DIR}/port-forward.sh" \
            "$KUBECONFIG_PATH" "$LOCAL_PORT" "$PF_PID_FILE" "${LOG_DIR}/port-forward.log"

        python3 "$SCRAPER" \
            --url "$BASE_URL" \
            --output-dir "$METRICS_DIR" \
            --journal "$SCRAPE_JOURNAL" \
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
            "${SCRIPT_DIR}/port-forward-stop.sh" "$PF_PID_FILE"
            exit 1
        fi

        echo "=== Scraper started (PID ${SCRAPER_PID}, output: ${METRICS_DIR}/<index>.om, journal: ${SCRAPE_JOURNAL}, log: ${SCRAPER_LOG_FILE}, source: ${BASE_URL})"
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

        "${SCRIPT_DIR}/port-forward-stop.sh" "$PF_PID_FILE"
        ;;
esac

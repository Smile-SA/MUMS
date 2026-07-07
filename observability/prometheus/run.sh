#!/bin/bash
# Manages observability: Prometheus port-forward + scraper.
# Usage:
#   ./run.sh start <kubeconfig> <output_dir>
#   ./run.sh stop  <kubeconfig>
#
# frequency_seconds / local_port / timeout_seconds are read from this
# module's own scenario-config section (BENCHMARK_COMPONENT_CONFIG).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PROMETHEUS_DIR="$SCRIPT_DIR/../../utils/prometheus"
SCRAPER="$SCRIPT_DIR/../../utils/scraper/scraper.py"
source "${REPO_ROOT}/scripts/lib/component_config.sh"

ACTION=$1
shift

case "$ACTION" in

    start)
        KUBECONFIG=$1
        OUTPUT_DIR=$2
        shift 2

        if [ -z "$KUBECONFIG" ] || [ -z "$OUTPUT_DIR" ]; then
            echo "Usage: $0 start <kubeconfig> <output_dir>" >&2
            exit 1
        fi

        if [ ! -f "$KUBECONFIG" ]; then
            echo "ERROR: kubeconfig '$KUBECONFIG' not found" >&2
            exit 1
        fi

        FREQUENCY="$(cfg_get '.frequency_seconds' '15')"

        NAME="$(basename "$KUBECONFIG")"

        BENCHMARK_LOG_DIR="${BENCHMARK_LOG_DIR:-/tmp}"
        BENCHMARK_PID_DIR="${BENCHMARK_PID_DIR:-/tmp}"
        BENCHMARK_METRICS_DIR="${BENCHMARK_METRICS_DIR:-${OUTPUT_DIR}}"

        mkdir -p "${BENCHMARK_LOG_DIR}" "${BENCHMARK_PID_DIR}" "${BENCHMARK_METRICS_DIR}"

        # Normalize artifact directories before passing them to helper scripts.
        BENCHMARK_LOG_DIR="$(cd "${BENCHMARK_LOG_DIR}" && pwd -P)"
        BENCHMARK_PID_DIR="$(cd "${BENCHMARK_PID_DIR}" && pwd -P)"
        BENCHMARK_METRICS_DIR="$(cd "${BENCHMARK_METRICS_DIR}" && pwd -P)"

        OUTPUT_FILE="${BENCHMARK_METRICS_DIR}/metrics.om"
        SCRAPER_LOG_FILE="${BENCHMARK_LOG_DIR}/scraper.log"
        SCRAPER_PID_FILE="${BENCHMARK_PID_DIR}/scraper-${NAME}.pid"

        PROMETHEUS_LOCAL_PORT="${PROMETHEUS_LOCAL_PORT:-$(cfg_get '.local_port' '9090')}"
        PROMETHEUS_BASE_URL="${PROMETHEUS_BASE_URL:-http://127.0.0.1:${PROMETHEUS_LOCAL_PORT}}"

        export PROMETHEUS_LOCAL_PORT
        export PROMETHEUS_BASE_URL
        export BENCHMARK_LOG_DIR
        export BENCHMARK_PID_DIR
        export BENCHMARK_METRICS_DIR

        if ! "$PROMETHEUS_DIR/port-forward.sh" "$KUBECONFIG" "$NAME"; then
            echo "ERROR: Unable to start Prometheus port-forwarding" >&2
            exit 1
        fi

        SCRAPE_METADATA_FILE="${BENCHMARK_METRICS_DIR}/scrapes.csv"
        PROMETHEUS_SCRAPE_TIMEOUT="${PROMETHEUS_SCRAPE_TIMEOUT:-$(cfg_get '.timeout_seconds' '10')}"

        python3 "$SCRAPER" \
            --url "$PROMETHEUS_BASE_URL" \
            --output "$OUTPUT_FILE" \
            --metadata-output "$SCRAPE_METADATA_FILE" \
            --frequency "$FREQUENCY" \
            --timeout "$PROMETHEUS_SCRAPE_TIMEOUT" \
            > /dev/null \
            2> "$SCRAPER_LOG_FILE" &

        echo $! > "$SCRAPER_PID_FILE"
        echo "=== Scraper started (PID $(cat "$SCRAPER_PID_FILE"), output: $OUTPUT_FILE, metadata: $SCRAPE_METADATA_FILE, log: $SCRAPER_LOG_FILE, source: $PROMETHEUS_BASE_URL)" >&2
        ;;

    stop)
        KUBECONFIG=$1
        if [ -z "$KUBECONFIG" ]; then
            echo "Usage: $0 stop <kubeconfig>" >&2
            exit 1
        fi

        NAME="$(basename "$KUBECONFIG")"

        BENCHMARK_PID_DIR="${BENCHMARK_PID_DIR:-/tmp}"
        mkdir -p "${BENCHMARK_PID_DIR}"
        BENCHMARK_PID_DIR="$(cd "${BENCHMARK_PID_DIR}" && pwd -P)"
        export BENCHMARK_PID_DIR

        PID_FILE="${BENCHMARK_PID_DIR}/scraper-${NAME}.pid"

        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            kill "$PID" 2>/dev/null \
                && echo "=== Scraper stopped (PID $PID)" >&2 \
                || echo "WARNING: scraper $PID already stopped" >&2
            rm -f "$PID_FILE"
        else
            echo "WARNING: no scraper PID file found for $NAME" >&2
        fi

        "$PROMETHEUS_DIR/port-forward-stop.sh" "$NAME"
        ;;

    *)
        echo "Usage: $0 <start|stop> ..." >&2
        echo "  start <kubeconfig> <output_dir>" >&2
        echo "  stop  <kubeconfig>" >&2
        exit 1
        ;;
esac

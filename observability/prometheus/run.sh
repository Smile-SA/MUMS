#!/bin/bash
# Gère l'observabilité : port-forward Prometheus + scraper.
# Usage:
#   ./run.sh start <kubeconfig> <output_dir> [--frequency=<seconds>]
#   ./run.sh stop  <kubeconfig>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROMETHEUS_DIR="$SCRIPT_DIR/../utils/prometheus"
SCRAPER="$SCRIPT_DIR/../utils/scraper/scraper.py"

ACTION=$1
shift

case "$ACTION" in

    start)
        KUBECONFIG=$1
        OUTPUT_DIR=$2
        shift 2

        if [ -z "$KUBECONFIG" ] || [ -z "$OUTPUT_DIR" ]; then
            echo "Usage: $0 start <kubeconfig> <output_dir> [--frequency=<seconds>]" >&2
            exit 1
        fi

        if [ ! -f "$KUBECONFIG" ]; then
            echo "ERREUR: kubeconfig '$KUBECONFIG' introuvable" >&2
            exit 1
        fi

        FREQUENCY=15
        for arg in "$@"; do
            case $arg in
                --frequency=*) FREQUENCY="${arg#--frequency=}" ;;
            esac
        done

        NAME=$(basename "$KUBECONFIG")
        mkdir -p "$OUTPUT_DIR"
        OUTPUT_FILE="$OUTPUT_DIR/metrics.om"

        "$PROMETHEUS_DIR/port-forward.sh" "$KUBECONFIG" "$NAME"

        python3 "$SCRAPER" http://127.0.0.1:9090 "$FREQUENCY" \
            > "$OUTPUT_FILE" \
            2> "/tmp/scraper-${NAME}.log" &

        echo $! > "/tmp/scraper-${NAME}.pid"
        echo "=== Scraper démarré (PID $(cat "/tmp/scraper-${NAME}.pid"), output: $OUTPUT_FILE)" >&2
        ;;

    stop)
        KUBECONFIG=$1
        if [ -z "$KUBECONFIG" ]; then
            echo "Usage: $0 stop <kubeconfig>" >&2
            exit 1
        fi

        NAME=$(basename "$KUBECONFIG")
        PID_FILE="/tmp/scraper-${NAME}.pid"

        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            kill "$PID" 2>/dev/null \
                && echo "=== Scraper arrêté (PID $PID)" >&2 \
                || echo "AVERTISSEMENT: scraper $PID déjà arrêté" >&2
            rm -f "$PID_FILE"
        else
            echo "AVERTISSEMENT: pas de PID scraper trouvé pour $NAME" >&2
        fi

        "$PROMETHEUS_DIR/port-forward-stop.sh" "$NAME"
        ;;

    *)
        echo "Usage: $0 <start|stop> ..." >&2
        echo "  start <kubeconfig> <output_dir> [--frequency=<seconds>]" >&2
        echo "  stop  <kubeconfig>" >&2
        exit 1
        ;;
esac

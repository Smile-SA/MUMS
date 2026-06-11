#!/bin/bash
# Génère du trafic sur Online Boutique depuis la machine hôte.
# Usage:
#   ./run.sh start <kubeconfig> <seed> [--shape=<nom>] [--duration=<minutes>] [options ...]
#   ./run.sh stop  <kubeconfig>
#
# Options (start) :
#   --shape=<nom>       Shape à utiliser (défaut: journee_type)
#   --duration=<min>    Durée d'un cycle en minutes (écrase DURATION_MINUTES du shape)

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
            echo "Usage: $0 start <kubeconfig> <seed> [--shape=<nom>] [--duration=<minutes>]" >&2
            exit 1
        fi

        if [ ! -f "$KUBECONFIG" ]; then
            echo "ERREUR: kubeconfig '$KUBECONFIG' introuvable" >&2
            exit 1
        fi

        PID_FILE="/tmp/traffic-$(basename "$KUBECONFIG").pid"
        if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
            echo "ERREUR: trafic déjà en cours (PID $(cat "$PID_FILE"))" >&2
            exit 1
        fi

        SHAPE="journee_type"
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
            echo "ERREUR: shape '$SHAPE' introuvable ($SHAPE_FILE)" >&2
            exit 1
        fi

        FRONTEND_URL="$(
            "${REPO_ROOT}/stacks/online-boutique/check_frontend.sh" "${KUBECONFIG}"
        )"
        echo "=== Cible Locust vérifiée: ${FRONTEND_URL} ===" >&2

        TARGET="http://${FRONTEND_URL}"
        echo "=== Trafic Online Boutique ===" >&2
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
            > "/tmp/traffic-$(basename "$KUBECONFIG").log" 2>&1 &

        echo $! > "$PID_FILE"
        echo "=== Trafic démarré (PID $(cat "$PID_FILE"), log: /tmp/traffic-$(basename "$KUBECONFIG").log)" >&2
        ;;

    stop)
        KUBECONFIG=$1
        if [ -z "$KUBECONFIG" ]; then
            echo "Usage: $0 stop <kubeconfig>" >&2
            exit 1
        fi

        PID_FILE="/tmp/traffic-$(basename "$KUBECONFIG").pid"
        if [ ! -f "$PID_FILE" ]; then
            echo "AVERTISSEMENT: pas de PID file trouvé ($PID_FILE)" >&2
            exit 0
        fi

        PID=$(cat "$PID_FILE")
        if kill "$PID" 2>/dev/null; then
            echo "=== Trafic arrêté (PID $PID)" >&2
        else
            echo "AVERTISSEMENT: processus $PID déjà arrêté" >&2
        fi
        rm -f "$PID_FILE"
        ;;

    *)
        echo "Usage: $0 <start|stop> ..." >&2
        echo "  start <kubeconfig> <seed> [--shape=<nom>] [--duration=<minutes>]" >&2
        echo "  stop  <kubeconfig>" >&2
        exit 1
        ;;
esac

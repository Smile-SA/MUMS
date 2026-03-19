#!/bin/bash
# Génère du trafic sur Online Boutique depuis la machine hôte.
# Le test tourne indéfiniment — c'est l'environnement qui gère l'arrêt.
# Usage: ./run.sh <kubeconfig> <seed> [--shape=<nom>] [--duration=<minutes>] [options ...]
#
# Options :
#   --shape=<nom>       Shape à utiliser (défaut: journee_type)
#   --duration=<min>    Durée d'un cycle en minutes (écrase DURATION_MINUTES du shape)

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TRAFFIC_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

KUBECONFIG=$1
SEED=$2
shift 2

if [ -z "$KUBECONFIG" ] || [ -z "$SEED" ]; then
    echo "Usage: $0 <kubeconfig> <seed> [--shape=<nom>] [--duration=<minutes>]" >&2
    exit 1
fi

if [ ! -f "$KUBECONFIG" ]; then
    echo "ERREUR: kubeconfig '$KUBECONFIG' introuvable" >&2
    exit 1
fi

SHAPE="journee_type"
DURATION=""
EXTRA_ARGS=()

for arg in "$@"; do
    case $arg in
        --shape=*)    SHAPE="${arg#--shape=}" ;;
        --duration=*) DURATION="${arg#--duration=}" ;;
        *)            EXTRA_ARGS+=("$arg") ;;
    esac
done

SHAPE_FILE="$TRAFFIC_DIR/shapes/${SHAPE}.py"
if [ ! -f "$SHAPE_FILE" ]; then
    echo "ERREUR: shape '$SHAPE' introuvable ($SHAPE_FILE)" >&2
    exit 1
fi

TARGET_IP=$(kubectl --kubeconfig "$KUBECONFIG" \
    get svc frontend-external -n online-boutique \
    -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null)

if [ -z "$TARGET_IP" ]; then
    echo "ERREUR: impossible de récupérer l'IP du frontend (cluster up ? stack déployée ?)" >&2
    exit 1
fi

TARGET="http://${TARGET_IP}"
echo "=== Trafic Online Boutique ===" >&2
echo "    Target  : $TARGET" >&2
echo "    Shape   : $SHAPE" >&2
echo "    Seed    : $SEED" >&2
[ -n "$DURATION" ] && echo "    Cycle   : ${DURATION} minutes" >&2

[ -n "$DURATION" ] && export DURATION_MINUTES="$DURATION"

cd "$TRAFFIC_DIR"
exec locust \
    -f "$SCRIPT_DIR/locustfile.py,$SHAPE_FILE" \
    --host "$TARGET" \
    --headless \
    --seed "$SEED" \
    "${EXTRA_ARGS[@]}"

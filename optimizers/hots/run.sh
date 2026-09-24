#!/usr/bin/env bash
# HOTS optimizer module (contract 1): runs HOTS + hots-connector as host-side
# processes against the live cluster, wired together over a per-run Kafka
# broker (utils/kafka).
#
# Usage:
#   run.sh start <kubeconfig> --log_dir <dir> --extras_dir <dir> [module args...]
#   run.sh stop  <kubeconfig> --log_dir <dir> --extras_dir <dir> [module args...]
#
# Module args (see module.yaml): --kafka_port, --prometheus_url,
# --k8s_workload_identity, --k8s_node_label_key, --namespace, --metric,
# --nb_clusters, --tick_seconds. See README.md for what each one means.
#
# Logs: <log_dir>/{hots,hots-connector,hots-moves-recorder}.log
# Extras: hots-config.json, hots-metrics.csv, moves.jsonl, PID files.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
UTILS_DIR="$(cd "${SCRIPT_DIR}/../../utils" && pwd -P)"

# Fixed, not user-configurable: runs are serial on a host, so a single
# well-known port for the connector's own HTTP control API is enough.
CONNECTOR_API_PORT=8189
TOPIC_DATA="hots_data"
TOPIC_MOVES="hots_moves"

usage() {
    echo "Usage:" >&2
    echo "  $0 start <kubeconfig> --log_dir <dir> --extras_dir <dir> [module args]" >&2
    echo "  $0 stop  <kubeconfig> --log_dir <dir> --extras_dir <dir> [module args]" >&2
    exit 1
}

ACTION="${1:-}"
case "$ACTION" in
    start|stop) ;;
    "") usage ;;
    *) echo "ERROR: unknown action '$ACTION'" >&2; usage ;;
esac
shift
[ "$#" -ge 1 ] || usage
KUBECONFIG_PATH="$1"
shift

LOG_DIR=""
EXTRAS_DIR=""
KAFKA_PORT=9092
PROMETHEUS_URL="http://127.0.0.1:9090"
K8S_WORKLOAD_IDENTITY="pod"
K8S_NODE_LABEL_KEY="kubernetes.io/hostname"
NAMESPACE="online-boutique"
METRIC="cpu"
NB_CLUSTERS=3
TICK_SECONDS=10

while [ "$#" -gt 0 ]; do
    case "$1" in
        --log_dir)               LOG_DIR="$2";               shift 2 ;;
        --extras_dir)            EXTRAS_DIR="$2";            shift 2 ;;
        --kafka_port)            KAFKA_PORT="$2";            shift 2 ;;
        --prometheus_url)        PROMETHEUS_URL="$2";        shift 2 ;;
        --k8s_workload_identity) K8S_WORKLOAD_IDENTITY="$2"; shift 2 ;;
        --k8s_node_label_key)    K8S_NODE_LABEL_KEY="$2";    shift 2 ;;
        --namespace)             NAMESPACE="$2";             shift 2 ;;
        --metric)                METRIC="$2";                shift 2 ;;
        --nb_clusters)           NB_CLUSTERS="$2";           shift 2 ;;
        --tick_seconds)          TICK_SECONDS="$2";          shift 2 ;;
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
LOG_DIR="$(cd "$LOG_DIR" && pwd -P)"
EXTRAS_DIR="$(cd "$EXTRAS_DIR" && pwd -P)"

# Kafka broker name, unique per run and identical for start and stop.
BROKER_NAME="hots-$(printf '%s' "$EXTRAS_DIR" | sha1sum | cut -c1-8)"

HOTS_PID_FILE="${EXTRAS_DIR}/hots.pid"
CONNECTOR_PID_FILE="${EXTRAS_DIR}/hots-connector.pid"
RECORDER_PID_FILE="${EXTRAS_DIR}/hots-moves-recorder.pid"
HOTS_CONFIG="${EXTRAS_DIR}/hots-config.json"

stop_pid_file() {
    local pid_file="$1" label="$2"
    [ -f "$pid_file" ] || { echo "WARNING: no PID file for ${label}" >&2; return 0; }
    local pid; pid="$(cat "$pid_file")"
    if kill "$pid" 2>/dev/null; then
        # Wait for a clean exit before the caller tears down shared
        # infrastructure (the Kafka broker) out from under it.
        for _ in $(seq 1 10); do
            kill -0 "$pid" 2>/dev/null || break
            sleep 0.5
        done
        kill -9 "$pid" 2>/dev/null || true
        echo "=== ${label} stopped (PID ${pid})"
    else
        echo "WARNING: ${label} (PID ${pid}) already stopped" >&2
    fi
    rm -f "$pid_file"
}

case "$ACTION" in
    start)
        if [ ! -f "$KUBECONFIG_PATH" ]; then
            echo "ERROR: kubeconfig '$KUBECONFIG_PATH' not found" >&2
            exit 1
        fi

        echo "=== Pre-flight: checking Prometheus reachability at ${PROMETHEUS_URL} ==="
        if ! curl -fsS --max-time 5 "${PROMETHEUS_URL}/-/healthy" >/dev/null 2>&1; then
            echo "ERROR: Prometheus not reachable at ${PROMETHEUS_URL}." >&2
            echo "  Confirm the observability module is running and that" >&2
            echo "  optimizer.prometheus_url matches observability.local_port." >&2
            exit 1
        fi

        echo "=== Starting per-run Kafka broker ==="
        "${UTILS_DIR}/kafka/broker.sh" start "$BROKER_NAME" "$KAFKA_PORT"

        # Pre-create both topics explicitly: a consumer subscribing to a topic
        # that doesn't exist yet raises UNKNOWN_TOPIC_OR_PART instead of
        # waiting -- hots-connector's tick loop (subscribed to topic_moves)
        # would crash on its very first tick, silently.
        for topic in "$TOPIC_DATA" "$TOPIC_MOVES"; do
            docker exec "benchmark-kafka-${BROKER_NAME}" /opt/kafka/bin/kafka-topics.sh \
                --bootstrap-server localhost:9092 \
                --create --if-not-exists --topic "$topic" \
                --partitions 1 --replication-factor 1
        done

        echo "=== Rendering HOTS config ==="
        python3 "${SCRIPT_DIR}/render_config.py" \
            "$HOTS_CONFIG" \
            --kubeconfig "$KUBECONFIG_PATH" \
            --kafka-port "$KAFKA_PORT" \
            --metric "$METRIC" \
            --nb-clusters "$NB_CLUSTERS" \
            --tick-seconds "$TICK_SECONDS" \
            --topic-data "$TOPIC_DATA" \
            --topic-moves "$TOPIC_MOVES" \
            --results-dir "$EXTRAS_DIR"

        echo "=== Starting hots-connector (kubernetes action backend) ==="
        # HOTSCONNECTOR_* is hots-connector's own configuration interface.
        # PROM_HOST_LABEL/PROM_QUERY_* override its "prometheus_kubernetes"
        # profile defaults: the platform's Prometheus labels the node as
        # `kubernetes_io_hostname`, and scrapes cadvisor every 1m, so the
        # default `rate(...[1m])` window is too tight to catch 2 samples.
        CONNECTOR_LOG="${LOG_DIR}/hots-connector.log"
        HOTSCONNECTOR_OBSERVATION_BACKEND=prometheus_kubernetes \
        HOTSCONNECTOR_TRANSPORT_BACKEND=kafka \
        HOTSCONNECTOR_ACTION_BACKEND=kubernetes \
        HOTSCONNECTOR_PROMETHEUS_URL="$PROMETHEUS_URL" \
        HOTSCONNECTOR_KAFKA_BOOTSTRAP_SERVERS="localhost:${KAFKA_PORT}" \
        HOTSCONNECTOR_KAFKA_TOPIC_DATA="$TOPIC_DATA" \
        HOTSCONNECTOR_KAFKA_TOPIC_MOVES="$TOPIC_MOVES" \
        HOTSCONNECTOR_KAFKA_GROUP_ID=hots_connector \
        HOTSCONNECTOR_PUBLISH_INTERVAL_SECONDS="$TICK_SECONDS" \
        HOTSCONNECTOR_K8S_KUBECONFIG_PATH="$KUBECONFIG_PATH" \
        HOTSCONNECTOR_K8S_NAMESPACE="$NAMESPACE" \
        HOTSCONNECTOR_K8S_WORKLOAD_IDENTITY="$K8S_WORKLOAD_IDENTITY" \
        HOTSCONNECTOR_K8S_NODE_LABEL_KEY="$K8S_NODE_LABEL_KEY" \
        HOTSCONNECTOR_PROM_WORKLOAD_LABEL=pod \
        HOTSCONNECTOR_PROM_HOST_LABEL=kubernetes_io_hostname \
        HOTSCONNECTOR_PROM_QUERY_CPU='sum by (pod, kubernetes_io_hostname) (rate(container_cpu_usage_seconds_total{container!=""}[2m]))' \
        HOTSCONNECTOR_PROM_QUERY_MEM_MB='sum by (pod, kubernetes_io_hostname) (container_memory_working_set_bytes{container!=""} / (1024*1024))' \
            hots-connector api --host 127.0.0.1 --port "$CONNECTOR_API_PORT" \
            > "$CONNECTOR_LOG" 2>&1 &
        echo $! > "$CONNECTOR_PID_FILE"

        echo "=== Waiting for hots-connector API... ==="
        CONNECTOR_READY=0
        for _ in $(seq 1 30); do
            if curl -fsS "http://127.0.0.1:${CONNECTOR_API_PORT}/health" >/dev/null 2>&1; then
                CONNECTOR_READY=1
                break
            fi
            sleep 1
        done
        if [ "$CONNECTOR_READY" -ne 1 ]; then
            echo "ERROR: hots-connector API did not become healthy" >&2
            cat "$CONNECTOR_LOG" >&2 || true
            exit 1
        fi

        echo "=== Checking hots-connector backends ==="
        CHECK_RESULT="$(curl -fsS "http://127.0.0.1:${CONNECTOR_API_PORT}/check" 2>/dev/null || echo '{}')"
        echo "$CHECK_RESULT"
        # Fail fast if any backend reported an error: HOTS would otherwise start,
        # get no telemetry, and exit cleanly after one empty poll.
        if echo "$CHECK_RESULT" | grep -q '"error'; then
            echo "ERROR: hots-connector /check reported backend failures (see above)." >&2
            exit 1
        fi

        if ! curl -fsS -X POST "http://127.0.0.1:${CONNECTOR_API_PORT}/stream/start" >/dev/null; then
            echo "ERROR: failed to start hots-connector's stream loop" >&2
            exit 1
        fi

        echo "=== Starting HOTS ==="
        HOTS_LOG="${LOG_DIR}/hots.log"
        # The KRaft single-node broker occasionally fails to elect a group
        # coordinator in time, causing HOTS to hit the bootstrap timeout. Give
        # it a second attempt before failing the start.
        HOTS_MAX_ATTEMPTS=2
        HOTS_STARTED=0
        for attempt in $(seq 1 "$HOTS_MAX_ATTEMPTS"); do
            : > "$HOTS_LOG"
            hots --config "$HOTS_CONFIG" > "$HOTS_LOG" 2>&1 &
            HOTS_PID=$!
            echo "$HOTS_PID" > "$HOTS_PID_FILE"

            sleep 15
            if kill -0 "$HOTS_PID" 2>/dev/null; then
                HOTS_STARTED=1
                break
            fi
            if grep -q "Kafka bootstrap failed" "$HOTS_LOG" 2>/dev/null; then
                echo "WARNING: HOTS bootstrap failed (attempt ${attempt}/${HOTS_MAX_ATTEMPTS}). Retrying..." >&2
                rm -f "$HOTS_PID_FILE"
                sleep 5
            else
                echo "ERROR: HOTS exited unexpectedly on attempt ${attempt}. Log: ${HOTS_LOG}" >&2
                cat "$HOTS_LOG" >&2
                exit 1
            fi
        done
        if [ "$HOTS_STARTED" -ne 1 ]; then
            echo "ERROR: HOTS failed to start after ${HOTS_MAX_ATTEMPTS} attempts." >&2
            cat "$HOTS_LOG" >&2
            exit 1
        fi

        echo "=== Starting moves recorder ==="
        : > "${EXTRAS_DIR}/moves.jsonl"
        python3 "${SCRIPT_DIR}/record_moves.py" \
            --bootstrap-servers "localhost:${KAFKA_PORT}" \
            --topic "$TOPIC_MOVES" \
            --output "${EXTRAS_DIR}/moves.jsonl" \
            > "${LOG_DIR}/hots-moves-recorder.log" 2>&1 &
        echo $! > "$RECORDER_PID_FILE"

        echo "=== HOTS optimizer started (connector PID $(cat "$CONNECTOR_PID_FILE"), hots PID $(cat "$HOTS_PID_FILE"), recorder PID $(cat "$RECORDER_PID_FILE")) ==="
        ;;

    stop)
        # Must succeed whatever is running: start may have failed half-way.

        # Best-effort: undo the nodeSelector patches before tearing the
        # connector down, then stop its tick loop.
        curl -fsS -X POST "http://127.0.0.1:${CONNECTOR_API_PORT}/kubernetes/reset-node-selectors" \
            >/dev/null 2>&1 || echo "WARNING: could not reset nodeSelector patches" >&2
        curl -fsS -X POST "http://127.0.0.1:${CONNECTOR_API_PORT}/stream/stop" \
            >/dev/null 2>&1 || true

        stop_pid_file "$HOTS_PID_FILE" "HOTS"
        # Give HOTS a moment to flush hots-metrics.csv before the connector
        # (and its telemetry topic) go away.
        sleep 2
        stop_pid_file "$CONNECTOR_PID_FILE" "hots-connector"
        stop_pid_file "$RECORDER_PID_FILE" "moves recorder"

        "${UTILS_DIR}/kafka/broker.sh" stop "$BROKER_NAME" || true
        ;;
esac

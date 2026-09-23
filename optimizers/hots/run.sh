#!/usr/bin/env bash
# Runs HOTS + the hots-connector as host-side processes against a live run,
# wired together over a per-run Kafka broker (utils/kafka).
#
# Usage:
#   ./run.sh deploy <kubeconfig>   # no-op: nothing is deployed into the cluster
#   ./run.sh start  <kubeconfig>
#   ./run.sh stop   <kubeconfig>
#
# kafka_port / prometheus_url / k8s_workload_identity / k8s_node_label_key /
# namespace / metric / nb_clusters / tick_seconds are read from this module's
# own scenario-config section (BENCHMARK_COMPONENT_CONFIG). See README.md for
# what each one means and why the defaults are pinned the way they are.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd -P)"
source "${REPO_ROOT}/scripts/lib/component_config.sh"

# Fixed, not user-configurable: this platform never runs two optimizers
# concurrently against the same host (one Kind cluster per run, run serially),
# so a single well-known port for the connector's own HTTP control API is
# enough -- same convention as observability/prometheus's default local_port.
CONNECTOR_API_PORT=8189

PYTHON_BIN="${PYTHON_BIN:-}"
if [ -z "${PYTHON_BIN}" ]; then
    if [ -x "${REPO_ROOT}/.venv/bin/python" ]; then
        PYTHON_BIN="${REPO_ROOT}/.venv/bin/python"
    else
        PYTHON_BIN="$(command -v python3 || true)"
    fi
fi

ACTION="${1:-}"
shift || true

stop_pid_file() {
    local pid_file="$1" label="$2"
    [ -f "$pid_file" ] || { echo "WARNING: no PID file for ${label}" >&2; return; }
    local pid; pid="$(cat "$pid_file")"
    if kill "$pid" 2>/dev/null; then
        # Wait for a clean exit before the caller tears down shared
        # infrastructure (the Kafka broker) out from under it.
        for _ in $(seq 1 10); do
            kill -0 "$pid" 2>/dev/null || break
            sleep 0.5
        done
        kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
        echo "=== ${label} stopped (PID ${pid})" >&2
    else
        echo "WARNING: ${label} (PID ${pid}) already stopped" >&2
    fi
    rm -f "$pid_file"
}

case "$ACTION" in
    deploy)
        echo "=== HOTS optimizer: nothing to deploy into the cluster ===" >&2
        echo "HOTS and the connector run as host-side processes; see 'start'/'stop'." >&2
        ;;

    start)
        KUBECONFIG_PATH="${1:-}"
        if [ -z "$KUBECONFIG_PATH" ]; then
            echo "Usage: $0 start <kubeconfig>" >&2
            exit 1
        fi
        if [ ! -f "$KUBECONFIG_PATH" ]; then
            echo "ERROR: kubeconfig '$KUBECONFIG_PATH' not found" >&2
            exit 1
        fi

        BENCHMARK_LOG_DIR="${BENCHMARK_LOG_DIR:-/tmp}"
        BENCHMARK_PID_DIR="${BENCHMARK_PID_DIR:-/tmp}"
        BENCHMARK_ARTIFACT_DIR="${BENCHMARK_ARTIFACT_DIR:-/tmp}"
        mkdir -p "${BENCHMARK_LOG_DIR}" "${BENCHMARK_PID_DIR}" "${BENCHMARK_ARTIFACT_DIR}"
        BENCHMARK_LOG_DIR="$(cd "${BENCHMARK_LOG_DIR}" && pwd -P)"
        BENCHMARK_PID_DIR="$(cd "${BENCHMARK_PID_DIR}" && pwd -P)"
        BENCHMARK_ARTIFACT_DIR="$(cd "${BENCHMARK_ARTIFACT_DIR}" && pwd -P)"

        NAME="$(basename "$KUBECONFIG_PATH")"

        KAFKA_PORT="$(cfg_get '.kafka_port' '9092')"
        PROMETHEUS_URL="$(cfg_get '.prometheus_url' 'http://127.0.0.1:9090')"
        K8S_WORKLOAD_IDENTITY="$(cfg_get '.k8s_workload_identity' 'pod')"
        K8S_NODE_LABEL_KEY="$(cfg_get '.k8s_node_label_key' 'kubernetes.io/hostname')"
        NAMESPACE="$(cfg_get '.namespace' 'online-boutique')"
        METRIC="$(cfg_get '.metric' 'cpu')"
        NB_CLUSTERS="$(cfg_get '.nb_clusters' '3')"
        TICK_SECONDS="$(cfg_get '.tick_seconds' '10')"

        TOPIC_DATA="hots_data"
        TOPIC_MOVES="hots_moves"

        # The observability module exposes its port via the port-forward; we can at
        # least check the connector can reach Prometheus before launching HOTS.
        echo "=== Pre-flight: checking Prometheus reachability at ${PROMETHEUS_URL} ===" >&2
        if ! curl -fsS --max-time 5 "${PROMETHEUS_URL}/-/healthy" >/dev/null 2>&1; then
            echo "ERROR: Prometheus not reachable at ${PROMETHEUS_URL}." >&2
            echo "  Confirm observability/prometheus port-forward is running and" >&2
            echo "  optimizer.prometheus_url matches observability.local_port." >&2
            exit 1
        fi

        echo "=== Starting per-run Kafka broker ===" >&2
        "${REPO_ROOT}/utils/kafka/broker.sh" start "$NAME" "$KAFKA_PORT"

        # Pre-create both topics explicitly: a producer auto-creates a topic
        # it publishes to, but a *consumer* subscribing to a topic that
        # doesn't exist yet raises UNKNOWN_TOPIC_OR_PART instead of waiting --
        # hots-connector's tick loop (subscribed to topic_moves) crashes on
        # its very first tick if that topic hasn't been created yet, silently
        # (POST /stream/start already returned 200 by the time the background
        # thread dies).
        KAFKA_CONTAINER="benchmark-kafka-${NAME}"
        for topic in "$TOPIC_DATA" "$TOPIC_MOVES"; do
            docker exec "$KAFKA_CONTAINER" /opt/kafka/bin/kafka-topics.sh \
                --bootstrap-server localhost:9092 \
                --create --if-not-exists --topic "$topic" \
                --partitions 1 --replication-factor 1 >&2
        done

        echo "=== Rendering HOTS config ===" >&2
        "$PYTHON_BIN" "${SCRIPT_DIR}/render_config.py" \
            "${BENCHMARK_ARTIFACT_DIR}/hots-config.json" \
            --kubeconfig "$KUBECONFIG_PATH" \
            --kafka-port "$KAFKA_PORT" \
            --metric "$METRIC" \
            --nb-clusters "$NB_CLUSTERS" \
            --tick-seconds "$TICK_SECONDS" \
            --topic-data "$TOPIC_DATA" \
            --topic-moves "$TOPIC_MOVES" \
            --results-dir "$BENCHMARK_ARTIFACT_DIR"

        echo "=== Starting hots-connector (kubernetes action backend) ===" >&2
        # PROM_HOST_LABEL/PROM_QUERY_* override hots-connector's built-in
        # "prometheus_kubernetes" profile defaults: this platform's Prometheus
        # chart (utils/helm/chart-repository/prometheus) labels the node as
        # `kubernetes_io_hostname`, not `node`, and scrapes the cadvisor job
        # every 1m -- a `rate(...[1m])` window (the built-in default) is too
        # tight to reliably catch 2 samples and returns empty.
        CONNECTOR_LOG="${BENCHMARK_LOG_DIR}/hots-connector.log"
        CONNECTOR_PID_FILE="${BENCHMARK_PID_DIR}/hots-connector-${NAME}.pid"
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

        echo "=== Waiting for hots-connector API... ===" >&2
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

        echo "=== Checking hots-connector backends ===" >&2
        CHECK_RESULT="$(curl -fsS "http://127.0.0.1:${CONNECTOR_API_PORT}/check" 2>/dev/null || echo '{}')"
        echo "$CHECK_RESULT" >&2

        # Fail fast if any backend reported an error: HOTS would otherwise start,
        # get no telemetry, and exit cleanly after one empty poll -- with no
        # obvious error pointing back to the connector misconfiguration.
        if echo "$CHECK_RESULT" | grep -q '"error'; then
            echo "ERROR: hots-connector /check reported backend failures (see above)." >&2
            echo "  Fix the reported errors before starting the optimizer." >&2
            exit 1
        fi

        curl -fsS -X POST "http://127.0.0.1:${CONNECTOR_API_PORT}/stream/start" >&2 \
            || echo "WARNING: failed to start hots-connector's stream loop" >&2

        echo "=== Starting HOTS ===" >&2
        HOTS_LOG="${BENCHMARK_LOG_DIR}/hots.log"
        HOTS_PID_FILE="${BENCHMARK_PID_DIR}/hots-${NAME}.pid"
        # The KRaft single-node broker occasionally fails to elect a group
        # coordinator in time, causing HOTS to hit the bootstrap timeout. Give
        # it a second attempt before failing the start.
        HOTS_MAX_ATTEMPTS=2
        HOTS_STARTED=0
        for attempt in $(seq 1 "$HOTS_MAX_ATTEMPTS"); do
            : > "$HOTS_LOG"
            "$(command -v hots)" --config "${BENCHMARK_ARTIFACT_DIR}/hots-config.json" \
                > "$HOTS_LOG" 2>&1 &
            HOTS_PID=$!
            echo "$HOTS_PID" > "$HOTS_PID_FILE"

            # Wait briefly and check for the known bootstrap failure
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
                echo "ERROR: HOTS exited unexpectedly on attempt ${attempt}. Check ${HOTS_LOG}." >&2
                cat "$HOTS_LOG" >&2
                exit 1
            fi
        done
        if [ "$HOTS_STARTED" -ne 1 ]; then
            echo "ERROR: HOTS failed to start after ${HOTS_MAX_ATTEMPTS} attempts." >&2
            cat "$HOTS_LOG" >&2
            exit 1
        fi

        echo "=== Starting moves recorder ===" >&2
        RECORDER_LOG="${BENCHMARK_LOG_DIR}/hots-moves-recorder.log"
        RECORDER_PID_FILE="${BENCHMARK_PID_DIR}/hots-moves-recorder-${NAME}.pid"
        : > "${BENCHMARK_ARTIFACT_DIR}/moves.jsonl"
        "$PYTHON_BIN" "${SCRIPT_DIR}/record_moves.py" \
            --bootstrap-servers "localhost:${KAFKA_PORT}" \
            --topic "$TOPIC_MOVES" \
            --output "${BENCHMARK_ARTIFACT_DIR}/moves.jsonl" \
            > "$RECORDER_LOG" 2>&1 &
        echo $! > "$RECORDER_PID_FILE"

        echo "=== HOTS optimizer started (connector PID $(cat "$CONNECTOR_PID_FILE"), hots PID $(cat "$HOTS_PID_FILE"), recorder PID $(cat "$RECORDER_PID_FILE")) ===" >&2
        ;;

    stop)
        KUBECONFIG_PATH="${1:-}"
        if [ -z "$KUBECONFIG_PATH" ]; then
            echo "Usage: $0 stop <kubeconfig>" >&2
            exit 1
        fi

        BENCHMARK_PID_DIR="${BENCHMARK_PID_DIR:-/tmp}"
        mkdir -p "${BENCHMARK_PID_DIR}"
        BENCHMARK_PID_DIR="$(cd "${BENCHMARK_PID_DIR}" && pwd -P)"

        NAME="$(basename "$KUBECONFIG_PATH")"
        KAFKA_PORT="$(cfg_get '.kafka_port' '9092')"

        # Generic contract (see benchmark_platform/provenance.py): any module
        # may drop a provenance-notes.json (a JSON list of strings) into its
        # own artifact dir, and the runner aggregates whatever it finds --
        # this module-specific caveat belongs here, not in core.
        BENCHMARK_ARTIFACT_DIR="${BENCHMARK_ARTIFACT_DIR:-/tmp}"
        mkdir -p "${BENCHMARK_ARTIFACT_DIR}"
        cat > "${BENCHMARK_ARTIFACT_DIR}/provenance-notes.json" <<'JSON'
["HOTS/hots-connector patch Deployment nodeSelectors in place while running. `stop` calls hots-connector's POST /kubernetes/reset-node-selectors to restore them, but that only covers patches made by the still-running process -- state is lost across a crash/restart. Verify nodeSelectors before reusing this cluster for another comparison."]
JSON

        # Best-effort: undo the sticky nodeSelector patches before tearing the
        # connector down, then stop its tick loop.
        curl -fsS -X POST "http://127.0.0.1:${CONNECTOR_API_PORT}/kubernetes/reset-node-selectors" \
            >&2 2>&1 || echo "WARNING: could not reset nodeSelector patches" >&2
        curl -fsS -X POST "http://127.0.0.1:${CONNECTOR_API_PORT}/stream/stop" \
            >/dev/null 2>&1 || true

        stop_pid_file "${BENCHMARK_PID_DIR}/hots-${NAME}.pid" "HOTS"
        # Give HOTS a moment to flush metrics.csv/hots.log on SIGTERM before
        # the connector (and its telemetry topic) go away.
        sleep 2
        stop_pid_file "${BENCHMARK_PID_DIR}/hots-connector-${NAME}.pid" "hots-connector"
        stop_pid_file "${BENCHMARK_PID_DIR}/hots-moves-recorder-${NAME}.pid" "moves recorder"

        "${REPO_ROOT}/utils/kafka/broker.sh" stop "$NAME"
        ;;

    *)
        echo "Usage: $0 <deploy|start|stop> <kubeconfig>" >&2
        exit 1
        ;;
esac

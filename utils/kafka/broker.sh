#!/usr/bin/env bash
# Starts/stops a single-node, ZooKeeper-less (KRaft) Kafka broker as one Docker
# container on the host, reachable by host-side processes at 127.0.0.1:<port>.
#
# Usage:
#   ./broker.sh start <name> [port] [image]   # defaults: 9092 (Kafka's), apache/kafka:3.7.1
#   ./broker.sh create-topic <name> <topic> [partitions]   # default: 1 partition
#   ./broker.sh stop  <name>
#
# The container is named benchmark-kafka-<name>: give each broker its own name
# (and port) to run several at once.

set -euo pipefail

usage() {
    echo "Usage: $0 start <name> [port] [image] | $0 create-topic <name> <topic> [partitions] | $0 stop <name>" >&2
}

ACTION="${1:-}"
NAME="${2:-}"
PORT="${3:-9092}"
IMAGE="${4:-apache/kafka:3.7.1}"

if [ -z "$ACTION" ] || [ -z "$NAME" ]; then
    usage
    exit 2
fi

CONTAINER="benchmark-kafka-${NAME}"

# Runs a Kafka tool inside the broker's container, against the address the
# broker advertises (localhost:<port>).
kafka_tool() {
    local tool="$1"; shift
    docker exec "$CONTAINER" sh -c \
        'tool="$1"; shift; exec "/opt/kafka/bin/${tool}" --bootstrap-server "${KAFKA_ADVERTISED_LISTENERS#PLAINTEXT://}" "$@"' \
        sh "$tool" "$@"
}

case "$ACTION" in
    start)
        if docker inspect "$CONTAINER" >/dev/null 2>&1; then
            echo "WARNING: stale Kafka broker container found (${CONTAINER}); removing it" >&2
            docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
        fi

        # Single-node KRaft (combined broker+controller) config. The broker
        # listens on PORT inside the container as well: the address it advertises
        # (localhost:PORT) is then valid for host-side clients and for the Kafka
        # tools run inside the container (kafka_tool). The controller listener
        # stays inside the container.
        # The offsets topic gets a single node's settings: with Kafka's defaults
        # (replication factor 3, 50 partitions) the broker cannot create
        # __consumer_offsets, and creating it by hand with another partition
        # count leaves most consumer groups without a coordinator: they
        # silently receive nothing.
        CONTROLLER_PORT=$(( PORT + 1 ))
        docker run -d --name "$CONTAINER" \
            -p "${PORT}:${PORT}" \
            -e KAFKA_NODE_ID=1 \
            -e KAFKA_PROCESS_ROLES=broker,controller \
            -e KAFKA_LISTENERS="PLAINTEXT://:${PORT},CONTROLLER://:${CONTROLLER_PORT}" \
            -e KAFKA_ADVERTISED_LISTENERS="PLAINTEXT://localhost:${PORT}" \
            -e KAFKA_CONTROLLER_LISTENER_NAMES=CONTROLLER \
            -e KAFKA_LISTENER_SECURITY_PROTOCOL_MAP="CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT" \
            -e KAFKA_CONTROLLER_QUORUM_VOTERS="1@localhost:${CONTROLLER_PORT}" \
            -e KAFKA_INTER_BROKER_LISTENER_NAME=PLAINTEXT \
            -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
            -e KAFKA_OFFSETS_TOPIC_NUM_PARTITIONS=1 \
            -e CLUSTER_ID="${CONTAINER}" \
            "$IMAGE" >/dev/null

        # The published port accepts connections as soon as the container
        # starts: ask the broker itself (the Kafka client retries until it
        # answers, 60 s at most).
        echo "=== Waiting for Kafka broker (${CONTAINER}) on 127.0.0.1:${PORT}..." >&2
        if ! kafka_tool kafka-topics.sh --list >/dev/null 2>&1; then
            echo "ERROR: Kafka broker failed to become ready within 60s" >&2
            docker logs "$CONTAINER" >&2 || true
            exit 1
        fi
        echo "=== Kafka broker ready at 127.0.0.1:${PORT} (container ${CONTAINER})" >&2
        ;;

    create-topic)
        # Topics are created explicitly: a consumer subscribing to a topic that
        # does not exist yet gets an error instead of waiting.
        TOPIC="${3:-}"
        PARTITIONS="${4:-1}"
        if [ -z "$TOPIC" ]; then
            usage
            exit 2
        fi
        kafka_tool kafka-topics.sh --create --if-not-exists --topic "$TOPIC" \
            --partitions "$PARTITIONS" --replication-factor 1 >&2
        ;;

    stop)
        if docker inspect "$CONTAINER" >/dev/null 2>&1; then
            docker rm -f "$CONTAINER" >/dev/null 2>&1
            echo "=== Kafka broker stopped (${CONTAINER})" >&2
        else
            echo "WARNING: no Kafka broker container found (${CONTAINER})" >&2
        fi
        ;;

    *)
        usage
        exit 2
        ;;
esac

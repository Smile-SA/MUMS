#!/usr/bin/env bash
# Starts/stops a single-node, ZooKeeper-less (KRaft) Kafka broker as one Docker
# container, for modules that need a live Kafka broker reachable from
# host-side processes (e.g. optimizers/hots).
#
# Usage:
#   ./broker.sh start <name> [port]   # default port: 9092
#   ./broker.sh stop  <name>
#
# The container is named benchmark-kafka-<name> so concurrent runs (named by
# kubeconfig basename, same convention as traffic-<name>.pid/scraper-<name>.pid)
# don't collide.

set -euo pipefail

IMAGE="apache/kafka:3.7.1"

usage() {
    echo "Usage: $0 <start|stop> <name> [port]" >&2
}

ACTION="${1:-}"
NAME="${2:-}"
PORT="${3:-9092}"

if [ -z "$ACTION" ] || [ -z "$NAME" ]; then
    usage
    exit 2
fi

CONTAINER="benchmark-kafka-${NAME}"

case "$ACTION" in
    start)
        if docker inspect "$CONTAINER" >/dev/null 2>&1; then
            echo "WARNING: stale Kafka broker container found (${CONTAINER}); removing it" >&2
            docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
        fi

        # Single-node KRaft (combined broker+controller) config. The container
        # always listens on 9092 internally; PORT is only how it's published to
        # the host and must match KAFKA_ADVERTISED_LISTENERS so that host-side
        # clients (which resolve broker metadata to this address) can reconnect.
        docker run -d --name "$CONTAINER" \
            -p "${PORT}:9092" \
            -e KAFKA_NODE_ID=1 \
            -e KAFKA_PROCESS_ROLES=broker,controller \
            -e KAFKA_LISTENERS="PLAINTEXT://:9092,CONTROLLER://:9093" \
            -e KAFKA_ADVERTISED_LISTENERS="PLAINTEXT://localhost:${PORT}" \
            -e KAFKA_CONTROLLER_LISTENER_NAMES=CONTROLLER \
            -e KAFKA_LISTENER_SECURITY_PROTOCOL_MAP="CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT" \
            -e KAFKA_CONTROLLER_QUORUM_VOTERS="1@localhost:9093" \
            -e KAFKA_INTER_BROKER_LISTENER_NAME=PLAINTEXT \
            -e CLUSTER_ID="${CONTAINER}" \
            "$IMAGE" >/dev/null

        echo "=== Waiting for Kafka broker (${CONTAINER}) on 127.0.0.1:${PORT}..." >&2
        for _ in $(seq 1 30); do
            if (exec 3<>"/dev/tcp/127.0.0.1/${PORT}") 2>/dev/null; then
                exec 3<&- 3>&- 2>/dev/null || true

                # This image's single-node KRaft combined broker+controller
                # never completes auto-creation of __consumer_offsets on its
                # own (observed consistently: the broker logs endless "Sent
                # auto-creation request... to the active controller" and the
                # topic never appears) -- without it, no consumer *group*
                # (subscribe(), as opposed to manual partition assign()) ever
                # gets a partition assignment, so every group-based consumer
                # silently receives nothing forever. Creating it explicitly
                # sidesteps the broken auto-creation path.
                docker exec "$CONTAINER" /opt/kafka/bin/kafka-topics.sh \
                    --bootstrap-server localhost:9092 \
                    --create --if-not-exists --topic __consumer_offsets \
                    --partitions 1 --replication-factor 1 \
                    --config cleanup.policy=compact >&2

                # Group-coordinator election for the new topic is normally
                # near-instant but was occasionally observed to still be
                # settling immediately after creation; this costs nothing and
                # narrows (does not eliminate) that window -- see the "known
                # limitation" note in optimizers/hots/README.md.
                sleep 3

                echo "=== Kafka broker ready at 127.0.0.1:${PORT} (container ${CONTAINER})" >&2
                exit 0
            fi
            sleep 1
        done

        echo "ERROR: Kafka broker failed to become ready within 30s" >&2
        docker logs "$CONTAINER" >&2 || true
        exit 1
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

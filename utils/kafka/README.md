# kafka

Util: a single-node Kafka broker (KRaft mode, without ZooKeeper), as one Docker
container on the host, for processes that also run on the host. It is reachable
at `127.0.0.1:<port>`.

## Scripts

Called by modules as `$MUMS_UTILS_PATH/kafka/broker.sh`.

- `broker.sh start <name> [port] [image]` (defaults: port `9092`, image
  `apache/kafka:3.7.1`): starts the container `benchmark-kafka-<name>` (removing
  a stale one with that name first), and waits until the broker answers (60 s at
  most; its logs are printed otherwise).
- `broker.sh create-topic <name> <topic> [partitions]` (default: 1 partition):
  creates a topic if it does not exist yet. Create the topics a consumer subscribes
  to before it starts: subscribing to a missing topic is an error, not a wait.
- `broker.sh stop <name>`: removes the container. Succeeds if it is not there.

Give each broker its own name and port to run several at once.

## Dependencies

docker (installed by hand; its daemon must run).

## Files

`broker.sh`, `util.yaml`.

## Known limitations

- The broker runs on the host, outside the cluster: it is not removed with the
  environment, only by `stop`. A run interrupted before `stop` leaves it running
  (remove it with `broker.sh stop <name>`, or `docker rm -f benchmark-kafka-<name>`).
- The Docker daemon is not checked before a run (no dependency script yet).

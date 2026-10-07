# kafka

Util: a single-node Kafka broker (KRaft mode, without ZooKeeper), as one Docker
container on the host, for processes that also run on the host. It is reachable
at `127.0.0.1:<port>`.

## Scripts

Called by modules as `$BENCHMARK_UTILS_PATH/kafka/broker.sh`.

- `broker.sh start <name> [port] [image]` (defaults: port `9092`, image
  `apache/kafka:3.7.1`): starts the container `benchmark-kafka-<name>` (removing
  a stale one with that name first), waits until the broker answers (30 s at
  most; its logs are printed otherwise), and creates the internal topic
  `__consumer_offsets` (see "Known limitations").
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
- With this image, a single-node broker never finishes creating
  `__consumer_offsets` on its own, so consumer groups would receive nothing:
  `start` creates it explicitly. Right after, the group coordinator may still be
  settling for a short while (narrowed by a short wait, not removed).
- The Docker daemon is not checked before a run (no dependency script yet).

#!/usr/bin/env python3
"""Persist HOTS moves from Kafka to a local JSONL file.

Neither HOTS (Kafka connector) nor hots-connector persists a moves log when
wired together over a live Kafka broker -- HOTS publishes moves to Kafka and
hots-connector consumes+applies them, but nothing writes them to disk. This
runs as an independent consumer group on the same moves topic (does not
interfere with hots-connector's own consumption), to keep HOTS's decisions in
the module's extras, for understanding a run (they are never evaluated).

Usage:
  record_moves.py --bootstrap-servers HOST:PORT --topic NAME --output FILE
"""

from __future__ import annotations

import argparse
import json
import signal
import sys
import time

from confluent_kafka import Consumer, KafkaError

_stop_requested = False


def _request_stop(signum, frame) -> None:
    global _stop_requested
    _stop_requested = True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bootstrap-servers", required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--group-id", default="mums-moves-recorder")
    args = parser.parse_args()

    signal.signal(signal.SIGTERM, _request_stop)
    signal.signal(signal.SIGINT, _request_stop)

    consumer = Consumer(
        {
            "bootstrap.servers": args.bootstrap_servers,
            "group.id": args.group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        }
    )
    consumer.subscribe([args.topic])

    try:
        with open(args.output, "a", encoding="utf-8") as out:
            while not _stop_requested:
                msg = consumer.poll(1.0)
                if msg is None:
                    continue
                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    print(f"[record_moves] consumer error: {msg.error()}", file=sys.stderr)
                    continue

                try:
                    payload = json.loads(msg.value())
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    print(f"[record_moves] skipping malformed message: {exc}", file=sys.stderr)
                    continue

                payload.setdefault("recorded_at", time.time())
                out.write(json.dumps(payload) + "\n")
                out.flush()
    finally:
        consumer.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

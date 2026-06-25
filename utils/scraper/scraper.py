#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import signal
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

import requests

RUNNING = True
MATCH_ALL_METRICS = '{__name__=~".+"}'
OPENMETRICS_ACCEPT_HEADER = "application/openmetrics-text; version=1.0.0"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def handle_signal(signum: int, frame: object) -> None:
    global RUNNING
    print("Stopping scraper...", file=sys.stderr)
    RUNNING = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Periodically scrape Prometheus federation output."
    )

    # Backward-compatible positional interface:
    #   scraper.py <prometheus_url> <frequency_seconds>
    parser.add_argument("prometheus_url", nargs="?")
    parser.add_argument("frequency_seconds", nargs="?", type=float)

    # New explicit interface:
    parser.add_argument("--url", dest="url")
    parser.add_argument("--output")
    parser.add_argument("--frequency", type=float)
    parser.add_argument("--metadata-output")
    parser.add_argument("--timeout", type=float, default=10.0)

    return parser.parse_args()


def build_federate_url(base_or_federate_url: str) -> tuple[str, dict[str, str] | None]:
    url = base_or_federate_url.rstrip("/")

    if "/federate" in url:
        # If caller already passed a full federate URL with match[] query params,
        # do not add params again.
        if "match[]" in url or "match%5B%5D" in url:
            return url, None
        return url, {"match[]": MATCH_ALL_METRICS}

    return f"{url}/federate", {"match[]": MATCH_ALL_METRICS}


def open_output_stream(output: str | None) -> tuple[TextIO, bool]:
    if output is None:
        return sys.stdout, False

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    return output_path.open("a", encoding="utf-8"), True


def open_metadata_writer(
    metadata_output: str | None,
) -> tuple[TextIO | None, csv.DictWriter | None]:
    if metadata_output is None:
        return None, None

    metadata_path = Path(metadata_output)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    metadata_file = metadata_path.open("a", encoding="utf-8", newline="")
    writer = csv.DictWriter(
        metadata_file,
        fieldnames=[
            "scrape_index",
            "started_at",
            "ended_at",
            "success",
            "http_status",
            "bytes_written",
            "error",
        ],
    )

    if metadata_path.stat().st_size == 0:
        writer.writeheader()
        metadata_file.flush()

    return metadata_file, writer


def main() -> int:
    args = parse_args()

    base_url = args.url or args.prometheus_url or "http://127.0.0.1:9090"
    frequency = (
        args.frequency
        if args.frequency is not None
        else args.frequency_seconds
        if args.frequency_seconds is not None
        else 15.0
    )

    federate_url, params = build_federate_url(base_url)

    print("=== Prometheus scraper ===", file=sys.stderr)
    print(f"    URL       : {base_url}", file=sys.stderr)
    print(f"    Federate  : {federate_url}", file=sys.stderr)
    print(f"    Frequency : {frequency}s", file=sys.stderr)
    print(f"    Timeout   : {args.timeout}s", file=sys.stderr)
    print(f"    Output    : {args.output or 'stdout'}", file=sys.stderr)
    print(f"    Metadata  : {args.metadata_output or 'disabled'}", file=sys.stderr)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    metrics_file, should_close_metrics = open_output_stream(args.output)
    metadata_file, metadata_writer = open_metadata_writer(args.metadata_output)

    scrape_index = 0

    try:
        while RUNNING:
            scrape_index += 1
            started_at = utc_now()
            success = False
            status = ""
            bytes_written = 0
            error = ""

            try:
                response = requests.get(
                    federate_url,
                    params=params,
                    headers={"Accept": OPENMETRICS_ACCEPT_HEADER},
                    timeout=args.timeout,
                )
                status = str(response.status_code)
                response.raise_for_status()

                payload = response.text

                metrics_file.write(f"# scrape_started_at {started_at}\n")
                metrics_file.write(payload)
                if not payload.endswith("\n"):
                    metrics_file.write("\n")
                metrics_file.write(f"# scrape_ended_at {utc_now()}\n")
                metrics_file.flush()

                bytes_written = len(payload.encode("utf-8"))
                success = True

            except Exception as exc:
                error = repr(exc)
                print(f"[WARN] scrape {scrape_index} failed: {error}", file=sys.stderr)

            if metadata_writer is not None and metadata_file is not None:
                metadata_writer.writerow(
                    {
                        "scrape_index": scrape_index,
                        "started_at": started_at,
                        "ended_at": utc_now(),
                        "success": str(success).lower(),
                        "http_status": status,
                        "bytes_written": bytes_written,
                        "error": error,
                    }
                )
                metadata_file.flush()

            sleep_until = time.monotonic() + frequency
            while RUNNING and time.monotonic() < sleep_until:
                time.sleep(min(0.5, sleep_until - time.monotonic()))

    finally:
        if should_close_metrics:
            metrics_file.close()
        if metadata_file is not None:
            metadata_file.close()

    print("Scraper stopped.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

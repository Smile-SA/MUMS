#!/usr/bin/env python3
"""Periodically scrape Prometheus's /federate endpoint (OpenMetrics).

Each scrape is written as its own file, <output-dir>/<index>.om (000001.om,
000002.om...): a complete, valid OpenMetrics exposition as returned by
Prometheus, one per scrape. A file appears only once complete (written to a
temporary file, then renamed). Reading all scrapes in order:

    cat <output-dir>/*.om

Scrapes start at a fixed rate (every --frequency seconds from the start), not
--frequency seconds after the previous one ended, so the period does not drift.

--journal (optional) records every scrape attempt, successful or not, as CSV:
scrape_index, started_at, ended_at, success, http_status, bytes_written, error.
"""

from __future__ import annotations

import argparse
import csv
import signal
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

RUNNING = True
MATCH_ALL_METRICS = '{__name__=~".+"}'
OPENMETRICS_ACCEPT_HEADER = "application/openmetrics-text; version=1.0.0"
JOURNAL_FIELDS = [
    "scrape_index",
    "started_at",
    "ended_at",
    "success",
    "http_status",
    "bytes_written",
    "error",
]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def handle_signal(signum: int, frame: object) -> None:
    global RUNNING
    print("Stopping scraper...", file=sys.stderr)
    RUNNING = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", required=True, help="Prometheus base URL.")
    parser.add_argument("--output-dir", required=True, help="Directory of the .om files.")
    parser.add_argument("--frequency", type=float, default=15.0, help="Seconds between scrapes.")
    parser.add_argument("--timeout", type=float, default=10.0, help="Request timeout (s).")
    parser.add_argument("--journal", help="CSV journal of every scrape attempt (optional).")
    return parser.parse_args()


def federate_request(base_url: str) -> tuple[str, dict[str, str]]:
    return f"{base_url.rstrip('/')}/federate", {"match[]": MATCH_ALL_METRICS}


def write_scrape(output_dir: Path, index: int, payload: str) -> int:
    """Write one scrape atomically; returns the number of bytes written."""
    if not payload.endswith("\n"):
        payload += "\n"
    if not payload.rstrip("\n").endswith("# EOF"):
        payload += "# EOF\n"
    data = payload.encode("utf-8")
    final = output_dir / f"{index:06d}.om"
    tmp = output_dir / f".{index:06d}.om.tmp"
    tmp.write_bytes(data)
    tmp.replace(final)
    return len(data)


def main() -> int:
    args = parse_args()
    url, params = federate_request(args.url)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print("=== Prometheus scraper ===", file=sys.stderr)
    print(f"    Federate  : {url}", file=sys.stderr)
    print(f"    Frequency : {args.frequency}s", file=sys.stderr)
    print(f"    Timeout   : {args.timeout}s", file=sys.stderr)
    print(f"    Output    : {output_dir}/<index>.om", file=sys.stderr)
    print(f"    Journal   : {args.journal or 'disabled'}", file=sys.stderr)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    journal_file = None
    journal = None
    if args.journal:
        journal_path = Path(args.journal)
        journal_path.parent.mkdir(parents=True, exist_ok=True)
        journal_file = journal_path.open("a", encoding="utf-8", newline="")
        journal = csv.DictWriter(journal_file, fieldnames=JOURNAL_FIELDS)
        if journal_path.stat().st_size == 0:
            journal.writeheader()
            journal_file.flush()

    scrape_index = 0
    next_start = time.monotonic()
    try:
        while RUNNING:
            scrape_index += 1
            started_at = utc_now()
            success, status, written, error = False, "", 0, ""
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers={"Accept": OPENMETRICS_ACCEPT_HEADER},
                    timeout=args.timeout,
                )
                status = str(response.status_code)
                response.raise_for_status()
                written = write_scrape(output_dir, scrape_index, response.text)
                success = True
            except Exception as exc:
                error = repr(exc)
                print(f"[WARN] scrape {scrape_index} failed: {error}", file=sys.stderr)

            if journal is not None and journal_file is not None:
                journal.writerow(
                    {
                        "scrape_index": scrape_index,
                        "started_at": started_at,
                        "ended_at": utc_now(),
                        "success": str(success).lower(),
                        "http_status": status,
                        "bytes_written": written,
                        "error": error,
                    }
                )
                journal_file.flush()

            # Fixed rate: the next scrape starts one period after this one
            # started; if a scrape overran, skip the missed slots.
            next_start += args.frequency
            now = time.monotonic()
            if next_start < now:
                next_start += args.frequency * int((now - next_start) // args.frequency + 1)
            while RUNNING and time.monotonic() < next_start:
                time.sleep(min(0.5, next_start - time.monotonic()))
    finally:
        if journal_file is not None:
            journal_file.close()

    print("Scraper stopped.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

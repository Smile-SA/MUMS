#!/usr/bin/env python3
"""
Scrapes all metrics from a Prometheus instance in OpenMetrics format.
Writes scraped data to stdout — caller is responsible for redirection.

Usage: scraper.py <prometheus_url> <frequency_seconds>
"""

import sys
import time
import signal
import requests


def main():
    if len(sys.argv) != 3:
        print("Usage: scraper.py <prometheus_url> <frequency_seconds>", file=sys.stderr)
        sys.exit(1)

    base_url = sys.argv[1]
    frequency = int(sys.argv[2])

    print("=== Prometheus scraper ===", file=sys.stderr)
    print(f"    URL       : {base_url}", file=sys.stderr)
    print(f"    Frequency : {frequency}s", file=sys.stderr)
    print("    Output    : stdout", file=sys.stderr)

    running = True

    def stop(signum, frame):
        nonlocal running
        print("Stopping scraper...", file=sys.stderr)
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    while running:
        start = time.time()
        try:
            resp = requests.get(
                f"{base_url}/federate",
                params={"match[]": "{__name__=~\".+\"}"},
                headers={"Accept": "application/openmetrics-text; version=1.0.0"},
            )
            resp.raise_for_status()
            sys.stdout.write(resp.text)
            sys.stdout.flush()
        except Exception as e:
            print(f"ERROR: scrape failed: {e}", file=sys.stderr)

        elapsed = time.time() - start
        sleep_time = max(0, frequency - elapsed)
        deadline = time.time() + sleep_time
        while running and time.time() < deadline:
            time.sleep(0.2)

    print("Scraper stopped.", file=sys.stderr)


if __name__ == "__main__":
    main()

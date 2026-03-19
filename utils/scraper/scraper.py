#!/usr/bin/env python3
"""
Scrapes all metrics from a Prometheus instance in OpenMetrics format.
Usage: scraper.py <prometheus_url> <frequency_seconds> <output_folder>
"""

import sys
import os
import time
import signal
import requests


def main():
    if len(sys.argv) != 4:
        print("Usage: scraper.py <prometheus_url> <frequency_seconds> <output_folder>", file=sys.stderr)
        sys.exit(1)

    base_url = sys.argv[1]
    frequency = int(sys.argv[2])
    output_folder = sys.argv[3]

    os.makedirs(output_folder, exist_ok=True)
    output_file = os.path.join(output_folder, "metrics.om")

    print(f"=== Prometheus scraper ===", file=sys.stderr)
    print(f"    URL       : {base_url}", file=sys.stderr)
    print(f"    Frequency : {frequency}s", file=sys.stderr)
    print(f"    Output    : {output_file}", file=sys.stderr)

    running = True
    def stop(signum, frame):
        nonlocal running
        print("Stopping scraper...", file=sys.stderr)
        running = False
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    with open(output_file, "w") as f:
        while running:
            start = time.time()
            try:
                resp = requests.get(
                    f"{base_url}/federate",
                    params={"match[]": "{__name__=~\".+\"}"},
                    headers={"Accept": "application/openmetrics-text; version=1.0.0"},
                )
                resp.raise_for_status()
                f.write(resp.text)
                f.flush()
            except Exception as e:
                print(f"ERROR: scrape failed: {e}", file=sys.stderr)
            elapsed = time.time() - start
            sleep_time = max(0, frequency - elapsed)
            deadline = time.time() + sleep_time
            while running and time.time() < deadline:
                time.sleep(0.2)

    print(f"Scraper stopped. Output: {output_file}", file=sys.stderr)


if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
csv_split.py
Reads a CSV on stdin and splits it into numbered files in a directory.

Usage: csv_split.py <directory> [--lines=N]

Output: <directory>/<basename>_1.csv, <directory>/<basename>_2.csv, ...
Each file is a self-contained CSV (header included), with at most N data rows
(default: 100000). A CSV with only a header gives one file with the header.
"""

import sys
from pathlib import Path


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--lines=")]
    lines = [a for a in sys.argv[1:] if a.startswith("--lines=")]
    if len(args) != 1:
        print("Usage: csv_split.py <directory> [--lines=N]", file=sys.stderr)
        return 1
    limit = int(lines[-1].split("=", 1)[1]) if lines else 100000
    directory = Path(args[0])
    directory.mkdir(parents=True, exist_ok=True)
    base = directory.name

    header = sys.stdin.readline()
    if not header:
        print(f"=== Split done: 0 file(s) in {directory}", file=sys.stderr)
        return 0

    count, rows, out = 1, 0, None

    def open_file(n):
        f = (directory / f"{base}_{n}.csv").open("w", encoding="utf-8", newline="")
        f.write(header)
        return f

    out = open_file(count)
    for line in sys.stdin:
        if rows == limit:
            out.close()
            count += 1
            rows = 0
            out = open_file(count)
        out.write(line)
        rows += 1
    out.close()
    print(f"=== Split done: {count} file(s) in {directory}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

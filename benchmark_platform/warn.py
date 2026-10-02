"""Warnings: something the core does not recognize (an unknown field in a
scenario or in a module's descriptor) is ignored, and reported once."""

from __future__ import annotations

import sys

_seen: set[str] = set()


def warn(message: str) -> None:
    if message not in _seen:
        _seen.add(message)
        print(f"[WARNING] {message}", file=sys.stderr)


def warn_unknown(keys, known, where: str) -> None:
    """Warn about the keys of `where` the core does not know (they are ignored)."""
    unknown = sorted(set(keys) - set(known))
    if unknown:
        warn(f"Unknown field(s) in {where}, ignored: {', '.join(map(str, unknown))}.")

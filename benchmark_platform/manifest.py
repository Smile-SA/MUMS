from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunManifest:
    def __init__(self, path: Path, initial: dict[str, Any]) -> None:
        self.path = path
        self.data = initial
        self.write()

    def update(self, **updates: Any) -> None:
        self.data.update(updates)
        self.write()

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.write()

    def append_event(self, event: dict[str, Any]) -> None:
        self.data.setdefault("events", []).append(event)
        self.write()

    def write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as stream:
            yaml.safe_dump(self.data, stream, sort_keys=False)

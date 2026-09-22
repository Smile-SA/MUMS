from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunPaths:
    root: Path
    config: Path
    manifest: Path
    logs: Path
    runtime: Path
    pids: Path
    traffic: Path
    metrics: Path
    kubernetes: Path
    post_processing: Path
    artifacts: Path

    @classmethod
    def create(cls, root: Path) -> RunPaths:
        paths = cls(
            root=root,
            config=root / "config.yaml",
            manifest=root / "manifest.yaml",
            logs=root / "logs",
            runtime=root / "runtime",
            pids=root / "runtime" / "pids",
            traffic=root / "traffic",
            metrics=root / "metrics",
            kubernetes=root / "kubernetes",
            post_processing=root / "post-processing",
            artifacts=root / "artifacts",
        )

        for path in (
            paths.logs,
            paths.runtime,
            paths.pids,
            paths.traffic,
            paths.metrics,
            paths.kubernetes,
            paths.post_processing,
            paths.artifacts,
        ):
            path.mkdir(parents=True, exist_ok=True)

        return paths

    def module_artifacts(self, name: str) -> Path:
        d = self.artifacts / name
        d.mkdir(parents=True, exist_ok=True)
        return d

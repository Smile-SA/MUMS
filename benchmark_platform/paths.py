from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunPaths:
    """Layout of a run directory.

    - `data/<format>/`: standard data, one directory per data format (e.g.
      `data/openmetrics/`). Modules that produce or consume standard data get
      the whole `data/` directory; each one writes only the directories of the
      formats it produces, and reads those it needs.
    - Per-module directories, private to each module: `logs/<module>/` and
      `extras/<module>/`.
    - Runner-owned: `manifest.yaml`, `runtime/`, `provenance/` (see provenance.py).
    """

    root: Path
    manifest: Path
    runtime: Path
    environment_result: Path
    kubeconfig: Path
    provenance: Path
    logs: Path
    extras: Path
    data: Path

    @classmethod
    def of(cls, root: Path) -> RunPaths:
        """The paths of the run at `root`, without creating anything."""
        runtime = root / "runtime"
        return cls(
            root=root,
            manifest=root / "manifest.yaml",
            runtime=runtime,
            environment_result=runtime / "environment-result",
            kubeconfig=runtime / "kubeconfig",
            provenance=root / "provenance",
            logs=root / "logs",
            extras=root / "extras",
            data=root / "data",
        )

    @classmethod
    def create(cls, root: Path) -> RunPaths:
        paths = cls.of(root)

        for path in (
            paths.runtime,
            paths.provenance,
            paths.logs,
            paths.extras,
            paths.data,
        ):
            path.mkdir(parents=True, exist_ok=True)

        return paths

    def module_logs(self, module_name: str) -> Path:
        path = self.logs / module_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def module_extras(self, module_name: str) -> Path:
        path = self.extras / module_name
        path.mkdir(parents=True, exist_ok=True)
        return path

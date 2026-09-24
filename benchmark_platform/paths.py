from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunPaths:
    """Layout of a run directory.

    - `outputs/<type>/`: contractual outputs, one directory per module type,
      readable by other modules without knowing which module produced them
      (e.g. `outputs/observability/metrics.om`).
    - Per-module directories, private to each module: `logs/<module>/` and
      `extras/<module>/`.
    - Runner-owned: `config.yaml`, `manifest.yaml`, `runtime/`, `kubernetes/`.
    """

    root: Path
    config: Path
    manifest: Path
    runtime: Path
    environment_result: Path
    kubeconfig: Path
    kubernetes: Path
    logs: Path
    extras: Path
    outputs: Path
    observability: Path
    traffic: Path
    post_processing: Path

    @classmethod
    def create(cls, root: Path) -> RunPaths:
        runtime = root / "runtime"
        paths = cls(
            root=root,
            config=root / "config.yaml",
            manifest=root / "manifest.yaml",
            runtime=runtime,
            environment_result=runtime / "environment-result",
            kubeconfig=runtime / "kubeconfig",
            kubernetes=root / "kubernetes",
            logs=root / "logs",
            extras=root / "extras",
            outputs=root / "outputs",
            observability=root / "outputs" / "observability",
            traffic=root / "outputs" / "traffic",
            post_processing=root / "outputs" / "post-processing",
        )

        for path in (
            paths.runtime,
            paths.kubernetes,
            paths.logs,
            paths.extras,
            paths.observability,
            paths.traffic,
            paths.post_processing,
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

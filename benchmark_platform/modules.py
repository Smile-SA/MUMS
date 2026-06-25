from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


class ModuleError(ValueError):
    pass


@dataclass(frozen=True)
class ModuleSpec:
    repo_root: Path
    module_path: Path
    descriptor: dict[str, Any]

    @property
    def relative_path(self) -> str:
        return self.module_path.relative_to(self.repo_root).as_posix()

    @property
    def name(self) -> str:
        return str(self.descriptor.get("name", self.relative_path))

    @property
    def type(self) -> str:
        return str(self.descriptor.get("type", ""))

    @property
    def entrypoint(self) -> Path:
        entrypoint = str(self.descriptor.get("entrypoint", "run.sh"))
        return self.module_path / entrypoint

    @property
    def entrypoint_relative(self) -> str:
        return self.entrypoint.relative_to(self.repo_root).as_posix()

    def command(self, action: str, *args: str) -> list[str]:
        if not self.entrypoint.exists():
            raise ModuleError(
                f"Module '{self.relative_path}' entrypoint does not exist: "
                f"{self.entrypoint_relative}"
            )
        return [f"./{self.entrypoint_relative}", action, *map(str, args)]

    def as_manifest_record(self) -> dict[str, str]:
        return {
            "name": self.name,
            "type": self.type,
            "path": self.relative_path,
            "entrypoint": self.entrypoint_relative,
        }


def load_module(
    repo_root: Path,
    module_path: str,
    *,
    expected_type: str | None = None,
) -> ModuleSpec:
    repo_root = repo_root.resolve()
    path = (repo_root / module_path).resolve()

    if not path.exists() or not path.is_dir():
        raise ModuleError(f"Module directory does not exist: {module_path}")

    try:
        path.relative_to(repo_root)
    except ValueError as exc:
        raise ModuleError(f"Module path escapes repository root: {module_path}") from exc

    descriptor_path = path / "module.yaml"
    if not descriptor_path.exists():
        raise ModuleError(f"Missing module descriptor: {module_path}/module.yaml")

    with descriptor_path.open("r", encoding="utf-8") as stream:
        descriptor = yaml.safe_load(stream) or {}

    if not isinstance(descriptor, dict):
        raise ModuleError(f"Invalid module descriptor: {descriptor_path}")

    module_type = str(descriptor.get("type", ""))
    if expected_type is not None and module_type != expected_type:
        raise ModuleError(
            f"Module '{module_path}' has type '{module_type}', "
            f"expected '{expected_type}'."
        )

    spec = ModuleSpec(repo_root=repo_root, module_path=path, descriptor=descriptor)

    if not spec.entrypoint.exists():
        raise ModuleError(
            f"Module '{module_path}' entrypoint does not exist: "
            f"{spec.entrypoint_relative}"
        )

    return spec

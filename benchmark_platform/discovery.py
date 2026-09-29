"""Module discovery: find a module (or util) from its name.

Modules are designated by the `name` of their `module.yaml`, never by path.
Discovery scans a list of root directories for `module.yaml` files and builds a
`name -> module directory` index:

- the platform repository itself;
- every directory listed in BENCHMARK_MODULE_PATHS (separated by ':', like
  PATH), for modules that live elsewhere.

A module's own subdirectories are not scanned (a module does not contain other
modules), and two modules with the same name are an error.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

MODULE_PATHS_ENV = "BENCHMARK_MODULE_PATHS"

# Directories never scanned: tooling, outputs, downloaded charts, and the parts
# of the platform repository that are not modules.
_SKIPPED_DIRS = frozenset(
    {
        "__pycache__",
        "node_modules",
        "venv",
        "output",
        "chart-repository",
        "benchmark_platform",
        "tests",
        "docs",
        "examples",
    }
)


class DiscoveryError(ValueError):
    pass


@dataclass(frozen=True)
class ModuleIndex:
    modules: dict[str, Path]

    def path(self, name: str) -> Path:
        if name not in self.modules:
            raise DiscoveryError(
                f"Unknown module '{name}'. Known modules: {', '.join(sorted(self.modules))}. "
                f"Modules outside the platform repository are found through {MODULE_PATHS_ENV}."
            )
        return self.modules[name]


def module_roots(repo_root: Path) -> list[Path]:
    roots = [repo_root.resolve()]
    for entry in os.environ.get(MODULE_PATHS_ENV, "").split(os.pathsep):
        if entry.strip():
            roots.append(Path(entry).expanduser().resolve())
    return roots


def discover(repo_root: Path) -> ModuleIndex:
    found: dict[str, Path] = {}
    for root in module_roots(repo_root):
        if not root.is_dir():
            raise DiscoveryError(f"Module root does not exist: {root}")
        for dirpath, dirnames, filenames in os.walk(root):
            current = Path(dirpath)
            if "module.yaml" in filenames:
                dirnames[:] = []  # a module does not contain other modules
                name = _module_name(current / "module.yaml")
                if name in found and found[name] != current:
                    raise DiscoveryError(
                        f"Two modules are named '{name}': {found[name]} and {current}."
                    )
                found[name] = current
                continue
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in _SKIPPED_DIRS]
    return ModuleIndex(found)


def _module_name(descriptor: Path) -> str:
    try:
        data = yaml.safe_load(descriptor.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise DiscoveryError(f"Unreadable module descriptor {descriptor}: {exc}") from exc
    name = data.get("name") if isinstance(data, dict) else None
    if not isinstance(name, str) or not name.strip():
        raise DiscoveryError(f"Module descriptor without a 'name': {descriptor}")
    return name.strip()

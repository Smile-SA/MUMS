"""Discovery: find a module or a util from its name.

Modules and utils are designated by their `name`, never by path.

- Modules (`module.yaml`) are searched in the directories of
  BENCHMARK_MODULE_PATHS (separated by ':').
- Utils (`util.yaml`) are searched in the directory BENCHMARK_UTILS_PATH, which
  modules also receive to call them.

Both come from the settings (settings.py, which exports them at the start of
every command): the core knows no directory of its own.

The two searches are independent: modules are only `module.yaml` files (wherever
they are, the utils directory included), utils only `util.yaml` files of the
utils directory (a `util.yaml` anywhere else is ignored).

A module's or util's own subdirectories are not scanned (it does not contain
others), and two of them with the same name are an error.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

MODULE_PATHS_ENV = "BENCHMARK_MODULE_PATHS"
UTILS_PATH_ENV = "BENCHMARK_UTILS_PATH"

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
    utils: dict[str, Path] = field(default_factory=dict)

    def path(self, name: str) -> Path:
        if name in self.modules:
            return self.modules[name]
        if name in self.utils:
            return self.utils[name]
        raise DiscoveryError(
            f"Unknown module or util '{name}'. Known modules: {', '.join(sorted(self.modules))}. "
            f"Known utils: {', '.join(sorted(self.utils)) or 'none'}. Modules are searched in "
            "module_paths, utils in utils_path (see 'benchmark-platform config')."
        )


def _required(variable: str) -> str:
    value = os.environ.get(variable, "").strip()
    if not value:
        raise DiscoveryError(
            f"{variable} is not set: run benchmark_platform/bootstrap.sh, or "
            "'benchmark-platform config set …'."
        )
    return value


def utils_path() -> Path:
    """The utils directory (BENCHMARK_UTILS_PATH)."""
    return Path(_required(UTILS_PATH_ENV)).expanduser().resolve()


def module_roots() -> list[Path]:
    """The directories where modules are searched (BENCHMARK_MODULE_PATHS)."""
    return [
        Path(entry).expanduser().resolve()
        for entry in _required(MODULE_PATHS_ENV).split(os.pathsep)
        if entry.strip()
    ]


def discover() -> ModuleIndex:
    modules: dict[str, Path] = {}
    for root in module_roots():
        if not root.is_dir():
            raise DiscoveryError(f"Module directory does not exist ({MODULE_PATHS_ENV}): {root}")
        _scan(root, "module.yaml", modules)
    utils: dict[str, Path] = {}
    utils_dir = utils_path()
    if not utils_dir.is_dir():
        raise DiscoveryError(f"Utils directory does not exist ({UTILS_PATH_ENV}): {utils_dir}")
    _scan(utils_dir, "util.yaml", utils)
    for name, path in utils.items():
        if name in modules:
            raise DiscoveryError(
                f"A module and a util are both named '{name}': {modules[name]} and {path}."
            )
    return ModuleIndex(modules, utils)


def _scan(root: Path, descriptor: str, found: dict[str, Path]) -> None:
    for dirpath, dirnames, filenames in os.walk(root):
        current = Path(dirpath)
        if descriptor in filenames:
            dirnames[:] = []  # a module or util does not contain others
            name = _module_name(current / descriptor)
            if name in found and found[name] != current:
                raise DiscoveryError(f"Two are named '{name}': {found[name]} and {current}.")
            found[name] = current
            continue
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in _SKIPPED_DIRS]


def _module_name(descriptor: Path) -> str:
    try:
        data = yaml.safe_load(descriptor.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        raise DiscoveryError(f"Unreadable module descriptor {descriptor}: {exc}") from exc
    name = data.get("name") if isinstance(data, dict) else None
    if not isinstance(name, str) or not name.strip():
        raise DiscoveryError(f"Module descriptor without a 'name': {descriptor}")
    return name.strip()

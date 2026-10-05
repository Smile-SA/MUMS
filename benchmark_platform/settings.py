"""Settings of the platform: where modules and utils are, and the environment
everything runs in. The one place that reads them and applies them (`apply`, at
the start of every command): everything else only sees environment variables.

Each setting is looked up, by priority:
  1. its environment variable (to override for one command, a CI, a test...);
  2. the configuration file: $BENCHMARK_CONFIG, or else
     $XDG_CONFIG_HOME/benchmark-platform/config.yaml (default:
     ~/.config/benchmark-platform/config.yaml), written by bootstrap.sh and
     edited with `benchmark-platform config`.

| Setting      | Variable                 | Meaning                                         |
|--------------|--------------------------|-------------------------------------------------|
| module_paths | BENCHMARK_MODULE_PATHS   | directories where modules are searched          |
| utils_path   | BENCHMARK_UTILS_PATH     | directory of the utils (also given to modules)  |
| env          | BENCHMARK_ENV            | file sourced at start (e.g. a venv's activate)  |

In a variable, module_paths are separated by ':' (like PATH); in the file, it is
a list. As with MANPATH, an empty element in the variable stands for the file's
value: "/mine" replaces it, "/mine:" adds the file's paths after, ":/mine" before.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

CONFIG_ENV = "BENCHMARK_CONFIG"
VARIABLES = {
    "module_paths": "BENCHMARK_MODULE_PATHS",
    "utils_path": "BENCHMARK_UTILS_PATH",
    "env": "BENCHMARK_ENV",
}


class SettingsError(RuntimeError):
    pass


@dataclass(frozen=True)
class Setting:
    key: str
    value: str | list[str] | None
    source: str  # "variable BENCHMARK_…", "file <path>", or "not set"


def config_file() -> Path:
    explicit = os.environ.get(CONFIG_ENV, "").strip()
    if explicit:
        return Path(explicit).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "benchmark-platform" / "config.yaml"


def read_file() -> dict:
    path = config_file()
    if not path.is_file():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise SettingsError(f"Invalid configuration file {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SettingsError(f"Invalid configuration file {path}: not a mapping.")
    return data


def write_file(data: dict) -> Path:
    path = config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = {k: v for k, v in data.items() if v not in (None, "", [])}
    path.write_text(yaml.safe_dump(clean, sort_keys=False), encoding="utf-8")
    return path


def get(key: str) -> Setting:
    if key not in VARIABLES:
        raise SettingsError(f"Unknown setting '{key}' (known: {', '.join(VARIABLES)}).")
    variable = VARIABLES[key]
    raw = os.environ.get(variable, "").strip()
    if raw and key == "module_paths":
        parts = raw.split(os.pathsep)
        if "" not in parts:
            return Setting(key, [p for p in parts if p.strip()], f"variable {variable}")
        from_file = _file_value(key) or []
        value: list[str] = []
        for part in parts:
            for path in (from_file if part == "" else [part]):
                if path not in value:
                    value.append(path)
        return Setting(key, value, f"variable {variable} and file {config_file()}")
    if raw:
        return Setting(key, raw, f"variable {variable}")
    value = _file_value(key)
    if value is None:
        return Setting(key, None, "not set")
    return Setting(key, value, f"file {config_file()}")


def _file_value(key: str) -> str | list[str] | None:
    value = read_file().get(key)
    if value in (None, "", []):
        return None
    if key == "module_paths":
        return [str(v) for v in (value if isinstance(value, list) else [value])]
    return str(value)


def require(key: str) -> Setting:
    setting = get(key)
    if setting.value is None:
        raise SettingsError(
            f"Setting '{key}' is not set: run benchmark_platform/bootstrap.sh, or "
            f"'benchmark-platform config set {key} …' (or set {VARIABLES[key]})."
        )
    return setting


def set_value(key: str, values: list[str]) -> Path:
    if key not in VARIABLES:
        raise SettingsError(f"Unknown setting '{key}' (known: {', '.join(VARIABLES)}).")
    data = read_file()
    if key == "module_paths":
        data[key] = [str(Path(v).expanduser().resolve()) for v in values]
    else:
        if len(values) != 1:
            raise SettingsError(f"'{key}' takes a single value.")
        data[key] = str(Path(values[0]).expanduser().resolve())
    return write_file(data)


def unset(key: str) -> Path:
    if key not in VARIABLES:
        raise SettingsError(f"Unknown setting '{key}' (known: {', '.join(VARIABLES)}).")
    data = read_file()
    data.pop(key, None)
    return write_file(data)


# What apply() found, before it exported anything (for `doctor`).
_ORIGINS: dict[str, Setting] = {}


def apply() -> None:
    """Applies the settings to this process, for everything it then runs:
    exports BENCHMARK_MODULE_PATHS and BENCHMARK_UTILS_PATH (a variable already
    set keeps precedence), then sources the `env` file, if any (e.g. a venv's
    activate: its bin/ goes first on PATH). BENCHMARK_ENV itself is not passed on:
    once sourced, nothing downstream needs it."""
    _ORIGINS.clear()
    for key in VARIABLES:
        _ORIGINS[key] = get(key)
    for key in ("module_paths", "utils_path"):
        value = _ORIGINS[key].value
        if isinstance(value, list):
            value = os.pathsep.join(value)
        if value is not None:
            os.environ[VARIABLES[key]] = value
    os.environ.pop(VARIABLES["env"], None)
    if _ORIGINS["env"].value:
        _source(Path(_ORIGINS["env"].value).expanduser().resolve())


def describe(key: str) -> Setting:
    """A setting as found before apply() exported anything."""
    return _ORIGINS.get(key) or get(key)


def _source(path: Path) -> None:
    """Source `path` (in bash) and take the resulting environment as this
    process's own."""
    if not path.is_file():
        raise SettingsError(f"env is not a file: {path}")
    result = subprocess.run(
        ["bash", "-c", 'source "$1" >/dev/null && env -0', "bash", str(path)],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip()
        raise SettingsError(f"Sourcing env ({path}) failed: {detail}")
    environment = {}
    for entry in result.stdout.split(b"\0"):
        if b"=" in entry:
            key, _, val = entry.decode(errors="replace").partition("=")
            environment[key] = val
    # Variables the file removed are removed here too; bash's own bookkeeping
    # variables are not imported.
    for key in set(os.environ) - set(environment):
        del os.environ[key]
    for key, val in environment.items():
        if key not in ("_", "SHLVL", "PWD", "OLDPWD"):
            os.environ[key] = val

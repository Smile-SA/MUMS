"""BENCHMARK_ENV: an environment for everything the platform runs.

If BENCHMARK_ENV names a file, the core sources it at startup (`source <file>`,
in bash) and takes the resulting environment as its own: every command it then
runs (modules' actions, dependency scripts, its own checks of the commands
modules need) sees that environment. A Python venv's `bin/activate` is one such
file; any script that sets up an environment works the same way.

Unset or empty: the core runs in the environment it was started from, unchanged.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ENV_FILE_ENV = "BENCHMARK_ENV"


class EnvironmentFileError(RuntimeError):
    pass


def load_environment() -> Path | None:
    """Source BENCHMARK_ENV (if set) and apply the resulting environment to this
    process. Returns the sourced file, or None."""
    value = os.environ.get(ENV_FILE_ENV, "").strip()
    if not value:
        return None
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise EnvironmentFileError(f"{ENV_FILE_ENV} is not a file: {path}")
    result = subprocess.run(
        ["bash", "-c", 'source "$1" >/dev/null && env -0', "bash", str(path)],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode(errors="replace").strip()
        raise EnvironmentFileError(f"Sourcing {ENV_FILE_ENV} ({path}) failed: {detail}")
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
    return path

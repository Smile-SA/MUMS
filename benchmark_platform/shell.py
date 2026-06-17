from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Mapping, Sequence


class CommandError(RuntimeError):
    def __init__(self, command: Sequence[str], returncode: int) -> None:
        super().__init__(f"Command failed with exit code {returncode}: {' '.join(command)}")
        self.command = list(command)
        self.returncode = returncode


def run_command(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    log_file: Path | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    if log_file is None:
        result = subprocess.run(list(command), cwd=str(cwd), env=merged_env, text=True, check=False)
    else:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8") as stream:
            stream.write(f"\n$ {' '.join(command)}\n")
            stream.flush()
            result = subprocess.run(
                list(command),
                cwd=str(cwd),
                env=merged_env,
                text=True,
                stdout=stream,
                stderr=subprocess.STDOUT,
                check=False,
            )

    if check and result.returncode != 0:
        raise CommandError(command, result.returncode)

    return result


def capture_stdout(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    check: bool = True,
) -> str:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    result = subprocess.run(
        list(command),
        cwd=str(cwd),
        env=merged_env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=None,
        check=False,
    )

    if check and result.returncode != 0:
        raise CommandError(command, result.returncode)

    return result.stdout.strip()

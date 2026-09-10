from __future__ import annotations

import os
import subprocess
import sys
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path


class CommandError(RuntimeError):
    def __init__(self, command: Sequence[str], returncode: int) -> None:
        super().__init__(
            f"Command failed with exit code {returncode}: {' '.join(command)}"
        )
        self.command = list(command)
        self.returncode = returncode


def run_command(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    log_file: Path | None = None,
    check: bool = True,
    verbose: bool = False,
    capture_stdout: bool = False,
) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()

    if env:
        merged_env.update(env)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)

    log_stream = (
        log_file.open("a", encoding="utf-8")
        if log_file is not None
        else None
    )

    try:
        if log_stream is not None:
            log_stream.write(f"\n$ {' '.join(command)}\n")
            log_stream.flush()

        # ------------------------------------------------------------------
        # Capture stdout separately.
        #
        # This is mainly used by env:create, where stdout contains the
        # kubeconfig path while stderr contains technical logs.
        # ------------------------------------------------------------------
        if capture_stdout:
            process = subprocess.Popen(
                list(command),
                cwd=str(cwd),
                env=merged_env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
            )

            captured_lines: list[str] = []

            def read_stdout() -> None:
                assert process.stdout is not None

                for line in process.stdout:
                    captured_lines.append(line)

                    if log_stream is not None:
                        log_stream.write(line)
                        log_stream.flush()

            def read_stderr() -> None:
                assert process.stderr is not None

                for line in process.stderr:
                    if log_stream is not None:
                        log_stream.write(line)
                        log_stream.flush()

                    if verbose:
                        sys.stdout.write(line)
                        sys.stdout.flush()

            stdout_thread = threading.Thread(target=read_stdout)
            stderr_thread = threading.Thread(target=read_stderr)

            stdout_thread.start()
            stderr_thread.start()

            returncode = process.wait()

            stdout_thread.join()
            stderr_thread.join()

            result = subprocess.CompletedProcess(
                args=list(command),
                returncode=returncode,
                stdout="".join(captured_lines),
            )

        # ------------------------------------------------------------------
        # No stdout capture.
        # ------------------------------------------------------------------
        elif verbose:
            process = subprocess.Popen(
                list(command),
                cwd=str(cwd),
                env=merged_env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
            )

            assert process.stdout is not None

            for line in process.stdout:
                if log_stream is not None:
                    log_stream.write(line)
                    log_stream.flush()

                sys.stdout.write(line)
                sys.stdout.flush()

            process.stdout.close()
            returncode = process.wait()

            result = subprocess.CompletedProcess(
                args=list(command),
                returncode=returncode,
            )

        # ------------------------------------------------------------------
        # Default mode: hide command output, but keep it in the log if
        # requested.
        # ------------------------------------------------------------------
        else:
            stdout_target = (
                log_stream
                if log_stream is not None
                else subprocess.DEVNULL
            )

            stderr_target = (
                subprocess.STDOUT
                if log_stream is not None
                else subprocess.DEVNULL
            )

            result = subprocess.run(
                list(command),
                cwd=str(cwd),
                env=merged_env,
                text=True,
                stdout=stdout_target,
                stderr=stderr_target,
                check=False,
            )

    finally:
        if log_stream is not None:
            log_stream.close()

    if check and result.returncode != 0:
        raise CommandError(command, result.returncode)

    return result
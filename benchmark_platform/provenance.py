"""Provenance of a run: what produced its results, to interpret, compare and
reproduce them. Written to <run>/provenance/, in two times, by the two functions
the runner calls. Everything is recorded as it comes (the scenario as given, the
raw output of standard commands, the files the system exposes), in its natural
format, without selecting or interpreting anything: nothing here knows a
specific module or tool, and modules have nothing to do for it.

- `record_start`, at the start of the run (what does not change during it, and
  stays available if the run fails):
    scenario.yaml          the scenario, as given;
    platform/commit.txt    `git rev-parse HEAD` in the platform's repository;
    platform/status.txt    `git status --porcelain` (uncommitted changes);
    platform/diff.patch    `git diff HEAD` (their content);
    modules.sha256         a digest of each module and util used (its directory),
                           in `sha256sum` format: `<digest>  <name>`;
    commands.sha256        a digest of the executable of each command they declare
                           (and the core's own), same format;
    commands/<name>.txt    the output of `<name> --version`;
    host/uname.txt         `uname -a`;
    host/os-release, host/cpuinfo, host/meminfo
                           copies of /etc/os-release, /proc/cpuinfo, /proc/meminfo.
- `record_end`, at the end of the run's wait, before anything stops (the system is
  still in the state that was measured):
    kubernetes/<kind>.yaml every listable kind of object (`kubectl get <kind> -A -o
                           yaml`), except those that only churn; events apart.
                           It holds the images that ran, with their digests, and
                           the nodes' versions.

Best effort: what cannot be recorded leaves its file with the error instead of
the output; provenance never fails a run.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPOSITORY = Path(__file__).resolve().parent.parent
# Kinds left out of the Kubernetes snapshot: they only churn, saying nothing of
# the run. Events are recorded apart.
EXCLUDED_KINDS = frozenset(
    {"leases.coordination.k8s.io", "endpointslices.discovery.k8s.io", "events",
     "events.events.k8s.io"}
)
# Not part of a module's content: local installs (hidden directories: .venv,
# .bin...) and caches, which differ from one machine to another.
SKIPPED_DIRECTORIES = frozenset({"__pycache__"})


def _output(command: list[str], *, timeout: float = 30, cwd: Path | None = None) -> str:
    """The command's output (stdout, then stderr), or why there is none."""
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout,
                                cwd=cwd, check=False)
    except FileNotFoundError:
        return f"{command[0]}: command not found\n"
    except (OSError, subprocess.SubprocessError) as exc:
        return f"{command[0]}: {exc}\n"
    output = result.stdout + result.stderr
    if result.returncode != 0:
        output += f"(exit code {result.returncode})\n"
    return output


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _copy(source: Path, target: Path) -> None:
    try:
        _write(target, source.read_text(encoding="utf-8", errors="replace"))
    except OSError as exc:
        _write(target, f"{source}: {exc}\n")


# ----------------------------------------------------------------------- start


def directory_digest(directory: Path) -> str:
    """sha256 over the relative paths and contents of a directory's files, hidden
    directories and caches excepted."""
    digest = hashlib.sha256()
    for root, dirs, files in os.walk(directory):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d not in SKIPPED_DIRECTORIES)
        for name in sorted(files):
            path = Path(root) / name
            digest.update(path.relative_to(directory).as_posix().encode() + b"\0")
            try:
                digest.update(hashlib.sha256(path.read_bytes()).digest())
            except OSError:
                digest.update(b"\0unreadable")
    return digest.hexdigest()


def _sha256_lines(digests: dict[str, str | None]) -> str:
    """`sha256sum` format; an entry without digest is written as a comment."""
    return "".join(
        f"{digest}  {name}\n" if digest else f"# {name}: not found\n"
        for name, digest in sorted(digests.items())
    )


def _executable_digest(command: str) -> str | None:
    found = shutil.which(command)
    if found is None:
        return None
    try:
        return hashlib.sha256(Path(found).resolve().read_bytes()).hexdigest()
    except OSError:
        return None


def record_start(
    directory: Path,
    scenario: Path,
    units: Iterable[tuple[str, Path, Iterable[str]]],
    core_commands: Iterable[str],
) -> None:
    """At the start of the run. `units`: (name, directory, declared commands) of
    every module and util the run uses."""
    directory.mkdir(parents=True, exist_ok=True)
    units = list(units)
    _copy(scenario, directory / "scenario.yaml")

    platform = directory / "platform"
    _write(platform / "commit.txt", _output(["git", "rev-parse", "HEAD"], cwd=REPOSITORY))
    _write(platform / "status.txt", _output(["git", "status", "--porcelain"], cwd=REPOSITORY))
    _write(platform / "diff.patch", _output(["git", "diff", "HEAD"], cwd=REPOSITORY))

    _write(directory / "modules.sha256",
           _sha256_lines({name: directory_digest(path) for name, path, _ in units}))

    commands = sorted({*core_commands, *(c for _, _, declared in units for c in declared)})
    _write(directory / "commands.sha256",
           _sha256_lines({c: _executable_digest(c) for c in commands}))
    for command in commands:
        version = _output([command, "--version"], timeout=5)
        _write(directory / "commands" / f"{command}.txt", version)

    host = directory / "host"
    _write(host / "uname.txt", _output(["uname", "-a"]))
    for source in ("/etc/os-release", "/proc/cpuinfo", "/proc/meminfo"):
        _copy(Path(source), host / Path(source).name)


# ------------------------------------------------------------------------- end


def record_end(directory: Path, kubeconfig: str) -> None:
    """At the end of the run's wait: a snapshot of every listable kind of object."""
    target = directory / "kubernetes"
    target.mkdir(parents=True, exist_ok=True)
    kubectl = ["kubectl", "--kubeconfig", kubeconfig]
    try:
        listed = subprocess.run([*kubectl, "api-resources", "--verbs=list", "-o", "name"],
                                capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        _write(target / "api-resources.txt", f"kubectl: {exc}\n")
        return
    if listed.returncode != 0:
        _write(target / "api-resources.txt", listed.stdout + listed.stderr)
        return
    kinds = sorted({k.strip() for k in listed.stdout.splitlines() if k.strip()} - EXCLUDED_KINDS)

    def snapshot(kind: str) -> None:
        objects = _output([*kubectl, "get", kind, "-A", "-o", "yaml"], timeout=60)
        _write(target / f"{kind}.yaml", objects)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(snapshot, [*kinds, "events"]))

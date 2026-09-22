"""Best-effort provenance capture: container image digests, Helm chart
versions, local tool versions, and any module-contributed caveats, recorded
into the run manifest so comparison numbers can be trusted and reproduced
later.

This module has no hardcoded knowledge of any specific module. A module that
wants to surface a provenance caveat (e.g. "I mutate cluster state that
won't be undone on a crash") writes `artifacts/<module-name>/provenance-
notes.json` (a JSON list of strings) any time before teardown; this file
generically aggregates whatever any module chose to report -- see "Optional
artifact conventions" in docs/output-format.md.

Every collector here is best-effort and must never raise -- a provenance
capture failure must never fail a benchmark run (see how it's called from
runner.py, wrapped again there for the same reason).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import yaml


def _run(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=30, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def collect_image_digests(pods_yaml_path: Path) -> list[dict[str, str]]:
    """Container image digests observed in the cluster, from the already-
    collected kubernetes/pods.yaml (no extra kubectl call needed)."""
    pods = _load_yaml(pods_yaml_path)
    items = pods.get("items", [])
    if not isinstance(items, list):
        return []

    seen: dict[tuple[str, str, str], str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata", {})
        status = item.get("status", {})
        namespace = str(metadata.get("namespace", ""))
        pod = str(metadata.get("name", ""))

        for status_field in (
            "initContainerStatuses",
            "containerStatuses",
            "ephemeralContainerStatuses",
        ):
            statuses = status.get(status_field, [])
            if not isinstance(statuses, list):
                continue
            for container_status in statuses:
                if not isinstance(container_status, dict):
                    continue
                name = str(container_status.get("name", ""))
                image_id = str(container_status.get("imageID", ""))
                if name and image_id:
                    seen[(namespace, pod, name)] = image_id

    return [
        {"namespace": ns, "pod": pod, "container": container, "image_id": image_id}
        for (ns, pod, container), image_id in sorted(seen.items())
    ]


def collect_chart_versions(kubeconfig: str) -> list[dict[str, str]] | None:
    """Helm release name/chart/version, best-effort. None if `helm` isn't
    usable (no releases installed via Helm, or the call otherwise fails)."""
    output = _run(["helm", "list", "-A", "-o", "json", "--kubeconfig", kubeconfig])
    if output is None:
        return None
    try:
        releases = json.loads(output)
    except json.JSONDecodeError:
        return None
    if not isinstance(releases, list):
        return None

    return [
        {
            "name": str(r.get("name", "")),
            "namespace": str(r.get("namespace", "")),
            "chart": str(r.get("chart", "")),
            "app_version": str(r.get("app_version", "")),
        }
        for r in releases
        if isinstance(r, dict)
    ]


def collect_tool_versions() -> dict[str, str | None]:
    """Best-effort local tool versions."""
    versions: dict[str, str | None] = {}

    kubectl_output = _run(["kubectl", "version", "-o", "json"])
    versions["kubectl"] = None
    if kubectl_output:
        try:
            data = json.loads(kubectl_output)
            versions["kubectl"] = data.get("clientVersion", {}).get("gitVersion")
        except json.JSONDecodeError:
            pass

    helm_output = _run(["helm", "version", "--short"])
    versions["helm"] = helm_output.strip() if helm_output else None

    kind_output = _run(["kind", "version"])
    versions["kind"] = kind_output.strip() if kind_output else None

    docker_output = _run(["docker", "version", "--format", "{{.Client.Version}}"])
    versions["docker"] = docker_output.strip() if docker_output else None

    return versions


def collect_module_notes(artifacts_dir: Path) -> list[str]:
    """Aggregate `provenance-notes.json` (a JSON list of strings) from every
    module's own `artifacts/<module-name>/` directory. Generic by
    construction -- this has no idea which modules exist or what they
    wrote; it just collects whatever any of them chose to report."""
    notes: list[str] = []
    if not artifacts_dir.is_dir():
        return notes

    for module_dir in sorted(artifacts_dir.iterdir()):
        notes_path = module_dir / "provenance-notes.json"
        if not notes_path.exists():
            continue
        try:
            data = json.loads(notes_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            notes.extend(str(note) for note in data)

    return notes


def build_provenance(
    *,
    pods_yaml_path: Path,
    kubeconfig: str,
    artifacts_dir: Path,
    cleanup_environment: bool,
) -> dict[str, Any]:
    notes: list[str] = []
    if not cleanup_environment:
        notes.append(
            "output.cleanup_environment is false -- this environment persists "
            "after the run. If any module mutates cluster state in place "
            "(e.g. a scheduler patching Deployment nodeSelectors), that "
            "state carries into whatever run reuses this cluster next."
        )
    notes.extend(collect_module_notes(artifacts_dir))

    return {
        "image_digests": collect_image_digests(pods_yaml_path),
        "chart_versions": collect_chart_versions(kubeconfig),
        "tool_versions": collect_tool_versions(),
        "notes": notes,
    }

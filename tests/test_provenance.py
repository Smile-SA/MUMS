from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from benchmark_platform.provenance import build_provenance, collect_module_notes


def test_collect_module_notes_aggregates_across_modules(tmp_path: Path) -> None:
    """provenance.py has no hardcoded knowledge of any module name -- any
    artifacts/<name>/provenance-notes.json is picked up generically."""
    artifacts_dir = tmp_path / "artifacts"
    (artifacts_dir / "optimizers.made-up-name").mkdir(parents=True)
    (artifacts_dir / "optimizers.made-up-name" / "provenance-notes.json").write_text(
        json.dumps(["note from a made-up optimizer module"]), encoding="utf-8"
    )
    (artifacts_dir / "traffic.online-boutique").mkdir(parents=True)
    (artifacts_dir / "traffic.online-boutique" / "provenance-notes.json").write_text(
        json.dumps(["note from the traffic module"]), encoding="utf-8"
    )

    notes = collect_module_notes(artifacts_dir)
    assert "note from a made-up optimizer module" in notes
    assert "note from the traffic module" in notes


def test_collect_module_notes_ignores_modules_without_notes(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    (artifacts_dir / "envs.kind").mkdir(parents=True)  # no provenance-notes.json here

    assert collect_module_notes(artifacts_dir) == []


def test_collect_module_notes_handles_missing_artifacts_dir(tmp_path: Path) -> None:
    assert collect_module_notes(tmp_path / "does-not-exist") == []


def test_build_provenance_adds_generic_cleanup_note_when_environment_persists(
    tmp_path: Path,
) -> None:
    with (
        patch("benchmark_platform.provenance.collect_chart_versions", return_value=None),
        patch("benchmark_platform.provenance.collect_tool_versions", return_value={}),
    ):
        provenance = build_provenance(
            pods_yaml_path=tmp_path / "pods.yaml",
            kubeconfig="/fake/kubeconfig",
            artifacts_dir=tmp_path / "artifacts",
            cleanup_environment=False,
        )

    assert any("cleanup_environment is false" in note for note in provenance["notes"])


def test_build_provenance_has_no_note_when_cleanup_environment_true(tmp_path: Path) -> None:
    with (
        patch("benchmark_platform.provenance.collect_chart_versions", return_value=None),
        patch("benchmark_platform.provenance.collect_tool_versions", return_value={}),
    ):
        provenance = build_provenance(
            pods_yaml_path=tmp_path / "pods.yaml",
            kubeconfig="/fake/kubeconfig",
            artifacts_dir=tmp_path / "artifacts",
            cleanup_environment=True,
        )

    assert provenance["notes"] == []

from pathlib import Path

from benchmark_platform.paths import RunPaths


def test_create_makes_artifacts_root(tmp_path: Path) -> None:
    paths = RunPaths.create(tmp_path / "run")

    assert paths.artifacts.is_dir()
    assert paths.artifacts == tmp_path / "run" / "artifacts"


def test_module_artifacts_creates_namespaced_dir(tmp_path: Path) -> None:
    paths = RunPaths.create(tmp_path / "run")

    module_dir = paths.module_artifacts("traffic.online-boutique")

    assert module_dir.is_dir()
    assert module_dir == paths.artifacts / "traffic.online-boutique"

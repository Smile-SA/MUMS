from __future__ import annotations

from benchmark_platform.paths import RunPaths


def test_layout(tmp_path):
    paths = RunPaths.create(tmp_path / "run")
    assert paths.data == tmp_path / "run" / "data"
    for path in (paths.data, paths.logs, paths.extras, paths.provenance, paths.runtime):
        assert path.is_dir()
    assert paths.module_logs("m") == tmp_path / "run" / "logs" / "m"
    assert paths.module_extras("m").is_dir()

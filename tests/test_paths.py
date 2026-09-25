from __future__ import annotations

from benchmark_platform.paths import RunPaths


def test_layout(tmp_path):
    paths = RunPaths.create(tmp_path / "run")
    assert paths.observability == tmp_path / "run" / "outputs" / "observability"
    assert paths.traffic == tmp_path / "run" / "outputs" / "traffic"
    assert paths.post_processing == tmp_path / "run" / "outputs" / "post-processing"
    for path in (
        paths.observability,
        paths.traffic,
        paths.post_processing,
        paths.logs,
        paths.extras,
    ):
        assert path.is_dir()
    assert paths.module_logs("m") == tmp_path / "run" / "logs" / "m"
    assert paths.module_extras("m").is_dir()

from __future__ import annotations

import pytest
import yaml

from benchmark_platform.config import ConfigError, ScenarioConfig, load_config
from benchmark_platform.dependencies import DependencyError
from benchmark_platform.runner import (
    ENVIRONMENT_ID_PATTERN,
    RunnerInterrupted,
    build_environment_id,
    run_scenario,
)
from benchmark_platform.shell import CommandError

FULL_RUN = [
    "environment create",
    "observability start",
    "stack deploy",
    "optimizer start",
    "traffic start",
    "traffic stop",
    "optimizer stop",
    "stack delete",
    "observability stop",
    "environment destroy",
    "post-processing run",
]


def _run(platform, **kwargs):
    return run_scenario(
        load_config(platform.write_scenario()), quiet=True, **kwargs
    )


def test_full_run_order_and_outputs(platform):
    run_dir = _run(platform)
    assert platform.read_calls() == FULL_RUN
    manifest = yaml.safe_load((run_dir / "manifest.yaml").read_text())
    assert manifest["status"] == "completed"
    assert ENVIRONMENT_ID_PATTERN.match(manifest["environment_id"])
    assert (run_dir / "logs" / "traffic" / "start.log").is_file()
    assert (run_dir / "data").is_dir()


def test_arguments_passed(platform):
    platform.scenario["traffic"]["shape"] = "night"
    path = platform.modules / "traffic" / "module.yaml"
    data = yaml.safe_load(path.read_text())
    data["args"] = {
        "shape": {"type": "string"},
        "rate": {"type": "positive_int", "description": "default: 5, applied by the module"},
        "extras_dir": {"type": "string"},
    }
    path.write_text(yaml.safe_dump(data))
    run_dir = _run(platform)
    calls = platform.calls.read_text().splitlines()
    line = next(ln for ln in calls if ln.startswith("traffic start"))
    assert f"{run_dir}/data" in line
    assert f"--extras_dir {run_dir}/extras/traffic" in line and "--log_dir" not in line
    assert "--shape night" in line and "--rate" not in line  # no default from the core
    stack_line = next(
        ln for ln in platform.calls.read_text().splitlines() if ln.startswith("stack deploy")
    )
    assert "--" not in stack_line


def test_failure_stops_launched_and_destroys(platform):
    (platform.modules / "stack" / "FAIL_deploy").touch()
    with pytest.raises(CommandError):
        _run(platform)
    assert platform.read_calls() == [
        "environment create",
        "observability start",
        "stack deploy",
        "stack delete",
        "observability stop",
        "environment destroy",
        "post-processing run",
    ]


def test_create_failure_still_destroys(platform):
    (platform.modules / "environment" / "FAIL_create").touch()
    with pytest.raises(CommandError):
        _run(platform)
    assert platform.read_calls() == [
        "environment create",
        "environment destroy",
        "post-processing run",
    ]


def test_interrupt_runs_stops_but_not_post_processing(platform, monkeypatch):
    from benchmark_platform import runner

    def interrupt(_):
        raise KeyboardInterrupt

    monkeypatch.setattr(runner, "_sleep_with_interrupt", interrupt)
    with pytest.raises(RunnerInterrupted):
        _run(platform)
    assert platform.read_calls() == FULL_RUN[:-1]


def test_no_cleanup_keeps_environment(platform):
    platform.scenario["output"]["cleanup_environment"] = False
    _run(platform)
    assert "environment destroy" not in platform.read_calls()


def test_nothing_created_when_invalid(platform, tmp_path):
    del platform.scenario["stack"]["module"]
    with pytest.raises(ConfigError):
        _run(platform)
    assert not (tmp_path / "runs").exists()
    assert platform.read_calls() == []


def test_missing_dependency_blocks_run(platform, tmp_path):
    path = platform.modules / "traffic" / "module.yaml"
    data = yaml.safe_load(path.read_text())
    data["dependencies"] = {"commands": ["definitely-not-installed"]}
    path.write_text(yaml.safe_dump(data))
    with pytest.raises(DependencyError):
        _run(platform)
    assert not (tmp_path / "runs").exists()


@pytest.mark.parametrize("name", ["basic", "Été à Paris !!", "日本", "x" * 200])
def test_environment_id_format(name, tmp_path):
    config = ScenarioConfig(tmp_path, {"scenario": {"name": name, "seed": 123456}})
    assert ENVIRONMENT_ID_PATTERN.match(build_environment_id(config, "run-id"))


def test_runner_args_not_settable_by_scenario(platform):
    platform.scenario["traffic"]["log_dir"] = "/tmp/x"
    with pytest.raises(ConfigError, match="provided by the runner"):
        _run(platform)


def test_relative_output_root_gives_absolute_paths(platform, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    platform.scenario["output"]["root_directory"] = "runs"
    run_dir = _run(platform)
    assert run_dir.is_absolute()
    line = next(
        ln for ln in platform.calls.read_text().splitlines() if ln.startswith("environment create")
    )
    assert str(tmp_path / "runs") in line


def test_registry_tracks_environments(platform, tmp_path):
    import shutil

    from benchmark_platform.cleanup import EnvironmentRegistry, clean_environments

    registry = EnvironmentRegistry()
    _run(platform)
    assert registry.entries() == []  # destroyed normally: unregistered

    platform.scenario["output"]["cleanup_environment"] = False
    run_dir = _run(platform)
    [entry] = registry.entries()
    assert entry.run_dir == run_dir

    shutil.rmtree(run_dir)  # losing the run output must not matter
    destroyed, errors = clean_environments(registry=registry)
    assert (destroyed, errors) == ([entry.environment_id], [])
    assert platform.read_calls()[-1] == "environment destroy"
    assert registry.entries() == []


def test_failed_destroy_stays_registered(platform):
    from benchmark_platform.cleanup import EnvironmentRegistry

    (platform.modules / "environment" / "FAIL_destroy").touch()
    _run(platform)
    assert len(EnvironmentRegistry().entries()) == 1


def test_incomplete_entry_removed_without_destroy(platform, tmp_path):
    from benchmark_platform.cleanup import EnvironmentRegistry, clean_environments

    registry = EnvironmentRegistry()
    broken = registry.root / "half-written"
    broken.mkdir(parents=True)
    (broken / "entry.yaml").write_text("environment_id: [unterminated", encoding="utf-8")
    assert registry.scan() == ([], [broken])
    assert clean_environments(registry=registry) == ([], [])
    assert not broken.exists()
    assert platform.read_calls() == []


def test_modules_get_utils_path(platform):
    script = platform.modules / "traffic" / "run.sh"
    script.write_text(
        script.read_text().replace(
            'echo "$(basename "$here") $*"',
            'echo "$(basename "$here") $* utils=$BENCHMARK_UTILS_PATH"',
        )
    )
    _run(platform)
    line = next(
        ln for ln in platform.calls.read_text().splitlines() if ln.startswith("traffic start")
    )
    assert f"utils={platform.root / 'utils'}" in line



def test_missing_core_prerequisite(platform, monkeypatch):
    import benchmark_platform.runner as runner_module

    monkeypatch.setattr(runner_module, "CORE_COMMANDS", ("definitely-not-installed",))
    with pytest.raises(DependencyError, match="prerequisite"):
        _run(platform)


def test_run_window_written(platform):
    run_dir = _run(platform)
    lines = (run_dir / "data" / "run-window" / "run-window.csv").read_text().splitlines()
    assert lines[0] == "start,end"
    start, end = (float(x) for x in lines[1].split(","))  # Unix seconds
    assert start <= end and 10**9 < start < 10**11


def test_post_processing_list_runs_in_order(platform):
    from tests.conftest import make_module

    make_module(platform.modules, "post2", "post-processing")
    platform.scenario["post-processing"] = [
        {"module": "post2"},
        {"module": "post-processing"},
    ]
    _run(platform)
    calls = platform.read_calls()
    assert calls[-2:] == ["post2 run", "post-processing run"]


def test_post_processing_listed_twice_runs_twice(platform):
    platform.scenario["post-processing"] = [
        {"module": "post-processing"},
        {"module": "post-processing"},
    ]
    _run(platform)
    assert platform.read_calls()[-2:] == ["post-processing run", "post-processing run"]


def test_post_processing_must_be_module_or_list(platform):
    platform.scenario["post-processing"] = "post-processing"
    with pytest.raises(ConfigError, match="must be a module or a list"):
        _run(platform)


def test_provenance_recorded(platform):
    root = _run(platform)
    target = root / "provenance"
    for name in ("scenario.yaml", "modules.sha256", "commands.sha256", "host/uname.txt",
                 "platform/commit.txt"):
        assert (target / name).is_file(), name
    assert (target / "kubernetes").is_dir()
    manifest = yaml.safe_load((root / "manifest.yaml").read_text())
    assert manifest["paths"]["provenance"] == str(target)
    assert any(e.get("type") == "provenance.collect" for e in manifest.get("events", []))


def test_provenance_failure_does_not_fail_the_run(platform, monkeypatch, capsys):
    from benchmark_platform import provenance

    def broken(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(provenance, "record_start", broken)
    monkeypatch.setattr(provenance, "record_end", broken)
    root = _run(platform)
    manifest = yaml.safe_load((root / "manifest.yaml").read_text())
    assert manifest["status"] == "completed"
    assert "disk full" in capsys.readouterr().err

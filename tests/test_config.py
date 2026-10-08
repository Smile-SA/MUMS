from __future__ import annotations

import pytest

from benchmark_platform.config import ConfigError, load_config


def test_valid(platform):
    assert load_config(platform.write_scenario()).seed == 42


def test_unknown_fields_only_warn(platform, capsys):
    from benchmark_platform.runner import prepare_scenario

    platform.scenario["observability"]["type"] = "prometheus"
    platform.scenario["scenario"]["colour"] = "red"
    platform.scenario["extra"] = 1
    prepare_scenario(load_config(platform.write_scenario()))  # valid: ignored
    err = capsys.readouterr().err
    assert "'observability'" in err and "type" in err
    assert "colour" in err and "extra" in err


def test_module_required(platform):
    del platform.scenario["stack"]["module"]
    with pytest.raises(ConfigError, match="stack.module"):
        load_config(platform.write_scenario())


def test_disruption_required(platform):
    del platform.scenario["disruption"]
    with pytest.raises(ConfigError, match="'disruption'"):
        load_config(platform.write_scenario())


def test_post_processing_optional(platform):
    del platform.scenario["post-processing"]
    load_config(platform.write_scenario())


@pytest.mark.parametrize("version", ["one", 2, None])
def test_bad_version_is_a_config_error(platform, version):
    platform.scenario["version"] = version
    with pytest.raises(ConfigError, match="version"):
        load_config(platform.write_scenario())

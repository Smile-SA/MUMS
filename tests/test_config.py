from __future__ import annotations

import pytest

from benchmark_platform.config import ConfigError, load_config


def test_valid(platform):
    assert load_config(platform.write_scenario()).seed == 42


def test_type_key_refused(platform):
    from benchmark_platform.runner import prepare_scenario

    platform.scenario["observability"]["type"] = "prometheus"
    with pytest.raises(ConfigError, match="Unknown field"):
        prepare_scenario(load_config(platform.write_scenario()), repo_root=platform.root)


def test_module_required(platform):
    del platform.scenario["stack"]["module"]
    with pytest.raises(ConfigError, match="stack.module"):
        load_config(platform.write_scenario())


def test_post_processing_optional(platform):
    del platform.scenario["post-processing"]
    load_config(platform.write_scenario())

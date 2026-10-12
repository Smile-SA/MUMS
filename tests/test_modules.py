from __future__ import annotations

import pytest
import yaml

from mums.modules import ModuleError, load_module_at
from tests.conftest import make_module


def test_valid_module_loads(tmp_path):
    make_module(tmp_path, "t", "traffic")
    module = load_module_at(tmp_path / "t", expected_type="traffic")
    assert module.type == "traffic" and module.name == "t"
    assert module.contract == 1
    assert module.supports("start") and module.supports("stop")


def test_name_required(tmp_path):
    path = make_module(tmp_path, "t", "traffic")
    data = yaml.safe_load((path / "module.yaml").read_text())
    del data["name"]
    (path / "module.yaml").write_text(yaml.safe_dump(data))
    with pytest.raises(ModuleError, match="'name' must be declared"):
        load_module_at(path)


def test_contract_defaults_to_1(tmp_path):
    path = make_module(tmp_path, "t", "traffic")
    data = yaml.safe_load((path / "module.yaml").read_text())
    del data["contract"]
    (path / "module.yaml").write_text(yaml.safe_dump(data))
    assert load_module_at(tmp_path / "t").contract == 1


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"type": "scheduler"}, "'type' must be one of"),
        ({"contract": 2}, "implements contract 1"),
        ({"entrypoint": ""}, "'entrypoint' must be declared"),
        ({"lifecycle": {}}, "'lifecycle' must be a non-empty mapping"),
        ({"lifecycle": {"stop": "<kubeconfig>"}}, "required action 'start'"),
        (
            {"lifecycle": {"start": "<kubeconfig> <seed> <data_dir>", "restart": "<x>"}},
            "'restart' is not part of the 'traffic' contract",
        ),
        ({"lifecycle": {"start": "<kubeconfig>"}}, "must be declared as"),
        ({"args": {"log_dir": {"type": "string", "required": True}}}, "provided by the runner"),
        ({"args": {"x": {"description": "no type"}}}, "must declare a type"),
        ({"args": {"x": {"type": "string", "description": 3}}}, "'description' of 'x'"),
    ],
)
def test_invalid_descriptor(tmp_path, overrides, message):
    make_module(tmp_path, "t", "traffic", **overrides)
    with pytest.raises(ModuleError, match=None) as exc:
        load_module_at(tmp_path / "t")
    assert message in str(exc.value)


def test_wrong_expected_type(tmp_path):
    make_module(tmp_path, "t", "traffic")
    with pytest.raises(ModuleError, match="expected 'observability'"):
        load_module_at(tmp_path / "t", expected_type="observability")


def test_command_signature(tmp_path):
    make_module(tmp_path, "t", "traffic")
    module = load_module_at(tmp_path / "t")
    command = module.command("start", ("kc", 42, "out"), options=("--shape", "day"))
    assert command[1:] == ["start", "kc", "42", "out", "--shape", "day"]
    with pytest.raises(ModuleError, match="expects"):
        module.command("start", ("kc",))


def test_unknown_keys_only_warn(tmp_path, capsys):
    make_module(
        tmp_path,
        "t",
        "traffic",
        args={"x": {"type": "positive_int", "default": 5, "colour": "red"}},
        dependencies={"checks": ["x"]},
        extra_top_level=1,
    )
    load_module_at(tmp_path / "t")  # loads: unknown fields are ignored
    err = capsys.readouterr().err
    assert "'default' of argument 'x'" in err
    assert "colour" in err and "checks" in err and "extra_top_level" in err

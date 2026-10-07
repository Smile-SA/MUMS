from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from benchmark_platform.dependencies import dependency_problems
from benchmark_platform.discovery import ModuleIndex
from benchmark_platform.schema import arg_schema_problems
from benchmark_platform.warn import warn_unknown

CONTRACT_VERSION = 1
DESCRIPTOR_KEYS = frozenset(
    {"name", "type", "contract", "entrypoint", "lifecycle", "args", "dependencies", "description"}
)


class ModuleError(ValueError):
    pass


@dataclass(frozen=True)
class ActionContract:
    positionals: tuple[str, ...]
    required: bool

    @property
    def signature(self) -> str:
        return " ".join(f"<{name}>" for name in self.positionals)


# Module contract, version 1: actions of each module type, their positional
# arguments, and whether the module must implement them. Every action then
# receives the named arguments declared in the module's `args:` (runner-provided
# ones such as --log_dir / --extras_dir only if declared).
TYPE_CONTRACTS: dict[str, dict[str, ActionContract]] = {
    "environment": {
        "create": ActionContract(("seed", "id", "output_file"), required=True),
        "destroy": ActionContract(("id",), required=True),
    },
    "stack": {
        "deploy": ActionContract(("kubeconfig", "seed"), required=True),
        "delete": ActionContract(("kubeconfig",), required=False),
    },
    "observability": {
        "start": ActionContract(("kubeconfig", "data_dir"), required=True),
        "stop": ActionContract(("kubeconfig",), required=False),
    },
    "traffic": {
        "start": ActionContract(("kubeconfig", "seed", "data_dir"), required=True),
        "stop": ActionContract(("kubeconfig",), required=False),
    },
    "optimizer": {
        "start": ActionContract(("kubeconfig",), required=True),
        "stop": ActionContract(("kubeconfig",), required=False),
    },
    "disruption": {
        "start": ActionContract(("kubeconfig", "seed"), required=True),
        "stop": ActionContract(("kubeconfig",), required=False),
    },
    "post-processing": {
        "run": ActionContract(("data_dir",), required=True),
    },
}

# Launch and stop action of each type (post-processing is one-shot: no stop).
LAUNCH_ACTIONS = {
    "environment": "create",
    "stack": "deploy",
    "observability": "start",
    "traffic": "start",
    "optimizer": "start",
    "disruption": "start",
    "post-processing": "run",
}
STOP_ACTIONS = {
    "environment": "destroy",
    "stack": "delete",
    "observability": "stop",
    "traffic": "stop",
    "optimizer": "stop",
    "disruption": "stop",
}


@dataclass(frozen=True)
class ModuleSpec:
    module_path: Path
    descriptor: dict[str, Any]

    @property
    def name(self) -> str:
        return str(self.descriptor["name"])

    @property
    def type(self) -> str:
        return str(self.descriptor.get("type", ""))

    @property
    def contract(self) -> int:
        return int(self.descriptor.get("contract", CONTRACT_VERSION))

    @property
    def entrypoint(self) -> Path:
        return self.module_path / str(self.descriptor["entrypoint"])

    @property
    def lifecycle(self) -> dict[str, Any]:
        return dict(self.descriptor["lifecycle"])

    @property
    def arg_schema(self) -> dict[str, Any]:
        return dict(self.descriptor.get("args") or {})

    def supports(self, action: str) -> bool:
        return action in self.lifecycle

    def command(
        self,
        action: str,
        positionals: tuple[Any, ...],
        options: tuple[str, ...] = (),
    ) -> list[str]:
        contract = TYPE_CONTRACTS[self.type][action]
        if len(positionals) != len(contract.positionals):
            raise ModuleError(
                f"Action '{self.type}.{action}' expects {contract.signature}, "
                f"got {len(positionals)} positional argument(s)."
            )
        return [str(self.entrypoint), action, *map(str, positionals), *options]

    def as_manifest_record(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "contract": self.contract,
            "path": str(self.module_path),
            "entrypoint": str(self.entrypoint),
        }


def _validate_descriptor(descriptor: dict[str, Any], module_path: str) -> None:
    problems: list[str] = []

    name = descriptor.get("name")
    if not isinstance(name, str) or not name.strip():
        problems.append("'name' must be declared (modules are designated by name).")

    module_type = descriptor.get("type")
    if module_type not in TYPE_CONTRACTS:
        problems.append(
            f"'type' must be one of {', '.join(TYPE_CONTRACTS)} (got {module_type!r})."
        )

    contract = descriptor.get("contract", CONTRACT_VERSION)
    if contract != CONTRACT_VERSION:
        problems.append(
            f"'contract' is {contract!r}, this platform implements contract {CONTRACT_VERSION}."
        )

    entrypoint = descriptor.get("entrypoint")
    if not isinstance(entrypoint, str) or not entrypoint.strip():
        problems.append("'entrypoint' must be declared.")

    lifecycle = descriptor.get("lifecycle")
    if not isinstance(lifecycle, dict) or not lifecycle:
        problems.append("'lifecycle' must be a non-empty mapping.")
    elif module_type in TYPE_CONTRACTS:
        actions = TYPE_CONTRACTS[module_type]
        for action in lifecycle:
            if action not in actions:
                problems.append(
                    f"lifecycle action '{action}' is not part of the '{module_type}' "
                    f"contract (allowed: {', '.join(actions)})."
                )
        for action, contract_spec in actions.items():
            if action not in lifecycle:
                if contract_spec.required:
                    problems.append(f"lifecycle must declare the required action '{action}'.")
                continue
            declared = " ".join(str(lifecycle[action]).split())
            if declared != contract_spec.signature:
                problems.append(
                    f"lifecycle action '{action}' must be declared as "
                    f"\"{contract_spec.signature}\" (got \"{declared}\")."
                )

    warn_unknown(descriptor, DESCRIPTOR_KEYS, f"{module_path}/module.yaml")
    problems.extend(
        f"args: {p}"
        for p in arg_schema_problems(descriptor.get("args") or {}, f"{module_path}/module.yaml")
    )
    problems.extend(
        f"dependencies: {p}" for p in dependency_problems(descriptor.get("dependencies"))
    )

    if problems:
        details = "\n  - ".join(problems)
        raise ModuleError(f"Invalid module '{module_path}':\n  - {details}")


def load_module(
    index: ModuleIndex,
    name: str,
    *,
    expected_type: str | None = None,
) -> ModuleSpec:
    """Load a module from its name (see discovery)."""
    return load_module_at(index.path(name), expected_type=expected_type)


def load_module_at(path: Path, *, expected_type: str | None = None) -> ModuleSpec:
    """Load the module in directory `path`."""
    path = path.resolve()
    descriptor_path = path / "module.yaml"
    if not descriptor_path.is_file():
        raise ModuleError(f"Missing module descriptor: {descriptor_path}")

    with descriptor_path.open("r", encoding="utf-8") as stream:
        descriptor = yaml.safe_load(stream) or {}

    if not isinstance(descriptor, dict):
        raise ModuleError(f"Invalid module descriptor: {descriptor_path}")

    _validate_descriptor(descriptor, str(path))

    if expected_type is not None and descriptor["type"] != expected_type:
        raise ModuleError(
            f"Module '{descriptor['name']}' has type '{descriptor['type']}', "
            f"expected '{expected_type}'."
        )

    spec = ModuleSpec(module_path=path, descriptor=descriptor)

    if not spec.entrypoint.is_file():
        raise ModuleError(
            f"Module '{descriptor['name']}' entrypoint does not exist: {spec.entrypoint}"
        )

    return spec

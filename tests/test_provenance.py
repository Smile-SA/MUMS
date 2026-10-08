from __future__ import annotations

import os

from benchmark_platform import provenance


def test_directory_digest_follows_content_only(tmp_path):
    module = tmp_path / "m"
    (module / "sub").mkdir(parents=True)
    (module / "run.sh").write_text("echo a\n")
    (module / "sub" / "f.txt").write_text("x\n")
    first = provenance.directory_digest(module)
    # Local installs and caches do not count.
    (module / ".venv").mkdir()
    (module / ".venv" / "lib").write_text("huge\n")
    (module / "__pycache__").mkdir()
    (module / "__pycache__" / "c.pyc").write_text("cache\n")
    assert provenance.directory_digest(module) == first
    (module / "run.sh").write_text("echo b\n")
    assert provenance.directory_digest(module) != first


def test_record_start(tmp_path):
    scenario = tmp_path / "scenario-in.yaml"
    scenario.write_text("scenario: {name: s}\n")
    module = tmp_path / "m"
    module.mkdir()
    (module / "run.sh").write_text("echo\n")
    target = tmp_path / "provenance"
    provenance.record_start(target, scenario, [("m", module, ["sh", "no-such-cmd"])], ["sh"])

    assert (target / "scenario.yaml").read_text() == scenario.read_text()
    modules = (target / "modules.sha256").read_text().splitlines()
    assert len(modules) == 1 and modules[0].endswith("  m") and len(modules[0].split()[0]) == 64
    commands = (target / "commands.sha256").read_text()
    assert "  sh\n" in commands and "# no-such-cmd: not found" in commands
    assert "command not found" in (target / "commands" / "no-such-cmd.txt").read_text()
    assert (target / "host" / "uname.txt").read_text().strip()
    for name in ("os-release", "cpuinfo", "meminfo"):
        assert (target / "host" / name).is_file()
    for name in ("commit.txt", "status.txt", "diff.patch"):
        assert (target / "platform" / name).is_file()
    assert (target / "python-packages.txt").is_file()


def test_record_end_snapshots_every_listable_kind(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    kubectl = bin_dir / "kubectl"
    kubectl.write_text(
        "#!/bin/sh\n"
        'case "$3" in\n'
        '  api-resources)\n'
        '    printf "pods\\nnodes\\nsecrets\\nleases.coordination.k8s.io\\nevents\\n" ;;\n'
        '  get) echo "kind: $4 $7" ;;\n'
        "esac\n"
    )
    kubectl.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")
    provenance.record_end(tmp_path / "provenance", "kubeconfig")
    files = sorted(p.name for p in (tmp_path / "provenance" / "kubernetes").iterdir())
    # Leases left out; secrets: names and types only, never their content.
    assert files == ["events.yaml", "nodes.yaml", "pods.yaml", "secrets.txt"]
    secrets = (tmp_path / "provenance" / "kubernetes" / "secrets.txt").read_text()
    assert "custom-columns=NAMESPACE:.metadata.namespace" in secrets

"""scripts/campaign.py, against the fake modules of conftest.py."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import yaml

CAMPAIGN = Path(__file__).resolve().parent.parent / "scripts" / "campaign.py"


def test_campaign_runs_every_scenario_each_round(platform, tmp_path):
    files = []
    for name in ("base", "opt"):
        data = {**platform.scenario, "scenario": {**platform.scenario["scenario"], "name": name}}
        path = tmp_path / f"{name}.yaml"
        path.write_text(yaml.safe_dump(data), encoding="utf-8")
        files.append(str(path))
    output = tmp_path / "campaign"
    result = subprocess.run(
        [sys.executable, str(CAMPAIGN), "-n", "2", "--output", str(output), *files],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    rows = list(csv.DictReader((output / "campaign.csv").open()))
    assert sorted((r["scenario"], r["seed"]) for r in rows) == [
        ("base", "42"), ("base", "43"), ("opt", "42"), ("opt", "43")]
    assert all(r["exit_code"] == "0" for r in rows)
    for name in ("base", "opt"):
        runs = sorted(output.glob(f"{name}-*-seed*"))
        assert len(runs) == 2 and all((run / "manifest.yaml").is_file() for run in runs)
    assert "-g base" in result.stdout and "-g opt" in result.stdout

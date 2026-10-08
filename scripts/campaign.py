#!/usr/bin/env python3
"""Run a measurement campaign: several scenarios, repeated, in shuffled rounds.

Each round runs every scenario once, in an order shuffled with a fixed seed (so that
no scenario always runs first, after the machine warmed up, etc.), with the round's
seed: the scenario's own seed + round index, the same for every scenario of a round.
All runs of the campaign go to one directory, so that each scenario's repetitions
are one glob pattern for `benchmark-platform compare -g`.

A failed run does not stop the campaign: it is reported at the end, and in
campaign.csv. Run it in the platform's environment:

  benchmark-platform exec -- python3 scripts/campaign.py -n 5 \\
      configs/baseline-online-boutique-15min.yaml \\
      configs/koordinator-online-boutique-15min.yaml

Then compare (the command is printed at the end):

  benchmark-platform compare -m report.md -c report.csv \\
      -g baseline 'output/campaign-<time>/baseline-online-boutique-15min-*' \\
      -g koordinator 'output/campaign-<time>/koordinator-online-boutique-15min-*'
"""

from __future__ import annotations

import argparse
import csv
import random
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import yaml


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("scenarios", nargs="+", type=Path, help="Scenario files.")
    parser.add_argument("-n", "--repetitions", type=int, default=5,
                        help="Rounds: runs of each scenario (default: 5).")
    parser.add_argument("--output", type=Path,
                        help="Directory of the campaign's runs (default: "
                        "output/campaign-<UTC time>).")
    parser.add_argument("--no-shuffle", action="store_true",
                        help="Keep the given order in every round.")
    parser.add_argument("--dry-run", action="store_true", help="Print the plan only.")
    args = parser.parse_args()

    scenarios = []
    for path in args.scenarios:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        scenarios.append((path, raw))
    names = [raw["scenario"]["name"] for _, raw in scenarios]
    if len(set(names)) != len(names):
        parser.error("two scenarios have the same name: their runs could not be told apart")

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = (args.output or Path("output") / f"campaign-{stamp}").resolve()
    rng = random.Random(0)
    plan = []
    for round_index in range(args.repetitions):
        order = list(range(len(scenarios)))
        if not args.no_shuffle:
            rng.shuffle(order)
        plan += [(round_index, i) for i in order]

    print(f"Campaign: {len(plan)} runs ({args.repetitions} rounds x {len(scenarios)} "
          f"scenarios), into {output}")
    for round_index, i in plan:
        seed = int(scenarios[i][1]["scenario"]["seed"]) + round_index
        print(f"  round {round_index + 1}: {names[i]} (seed {seed})")
    if args.dry_run:
        return 0

    output.mkdir(parents=True, exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory() as tmp:
        for number, (round_index, i) in enumerate(plan, start=1):
            path, raw = scenarios[i]
            seed = int(raw["scenario"]["seed"]) + round_index
            scenario = {**raw, "scenario": {**raw["scenario"], "seed": seed},
                        "output": {**raw["output"], "root_directory": str(output)}}
            copy = Path(tmp) / f"{names[i]}-seed{seed}.yaml"
            copy.write_text(yaml.safe_dump(scenario, sort_keys=False), encoding="utf-8")
            print(f"\n=== Run {number}/{len(plan)}: {names[i]}, round {round_index + 1}, "
                  f"seed {seed} ===", flush=True)
            run_dir = ""
            process = subprocess.Popen(
                [sys.executable, "-m", "benchmark_platform.cli", "run", str(copy)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            assert process.stdout is not None
            for line in process.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
                if line.startswith("Run: "):
                    run_dir = line[len("Run: "):].strip()
            code = process.wait()
            results.append((round_index + 1, names[i], seed, code, run_dir, str(path)))
            if code == 130:
                print("Interrupted: campaign stopped.", file=sys.stderr)
                break

    with (output / "campaign.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["round", "scenario", "seed", "exit_code", "run_dir", "scenario_file"])
        writer.writerows(results)

    failed = [r for r in results if r[3] != 0]
    print(f"\nCampaign done: {len(results) - len(failed)} completed, {len(failed)} failed "
          f"(details: {output / 'campaign.csv'}).")
    for r in failed:
        print(f"  FAILED: {r[1]} round {r[0]} seed {r[2]} (exit {r[3]}): {r[4]}")
    groups = " ".join(f"\\\n    -g {name} '{output}/{name}-*'" for name in names)
    print(f"\nCompare:\n  benchmark-platform compare -m report.md -c report.csv {groups}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

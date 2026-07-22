from __future__ import annotations

import argparse
import sys
from pathlib import Path

from benchmark_platform.compare import compare_runs, default_output_dir, write_report
from benchmark_platform.config import ConfigError, load_config
from benchmark_platform.runner import run_scenario


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="benchmark-platform")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="Validate a scenario configuration.")
    validate.add_argument("config", help="Path to scenario YAML file.")

    run = subparsers.add_parser("run", help="Run a scenario configuration.")
    run.add_argument("config", help="Path to scenario YAML file.")
    run.add_argument(
        "--repo-root", default=".", help="Repository root. Defaults to current directory."
    )

    compare = subparsers.add_parser(
        "compare", help="Compare two benchmark runs (e.g. baseline vs. optimized)."
    )
    compare.add_argument("baseline_run_dir", type=Path, help="Path to the baseline run directory.")
    compare.add_argument(
        "optimized_run_dir", type=Path, help="Path to the optimized run directory."
    )
    compare.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "Output directory. Default: "
            "<optimized_run_dir>/../comparisons/<baseline>__vs__<optimized>/"
        ),
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command == "compare":
            output_dir = args.output or default_output_dir(
                args.baseline_run_dir, args.optimized_run_dir
            )

            result = compare_runs(args.baseline_run_dir, args.optimized_run_dir)
            json_path, md_path = write_report(result, output_dir)

            print(result["headline"])
            print(f"Report: {md_path} ({json_path})")
            return 0

        config = load_config(args.config)

        if args.command == "validate":
            print(f"Valid scenario config: {config.path}")
            return 0

        if args.command == "run":
            run_dir = run_scenario(config, repo_root=Path(args.repo_root).resolve())
            print(f"Run completed: {run_dir}")
            return 0

        parser.error(f"Unsupported command: {args.command}")
        return 2

    except ConfigError as exc:
        print(f"[CONFIG ERROR] {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("[INTERRUPTED] Benchmark run interrupted by user.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

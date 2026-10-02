from __future__ import annotations

import argparse
import sys

from benchmark_platform.cleanup import EnvironmentRegistry, clean_environments
from benchmark_platform.config import ConfigError, load_config
from benchmark_platform.dependencies import (
    DependencyError,
    check_dependencies,
    install_dependencies,
)
from benchmark_platform.discovery import DiscoveryError, discover
from benchmark_platform.doctor import run_doctor
from benchmark_platform.environment import EnvironmentFileError, load_environment
from benchmark_platform.modules import ModuleError
from benchmark_platform.runner import prepare_scenario, run_scenario, utils_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="benchmark-platform")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate",
        help="Validate a scenario: config, modules and their dependencies.",
    )
    validate.add_argument("config", help="Path to scenario YAML file.")

    run = subparsers.add_parser("run", help="Run a scenario configuration.")
    run.add_argument("config", help="Path to scenario YAML file.")
    verbosity = run.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show component command output in the terminal.",
    )
    verbosity.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress benchmark progress output.",
    )

    deps = subparsers.add_parser(
        "deps", help="Install or check the dependencies of modules (by name), recursively."
    )
    deps_commands = deps.add_subparsers(dest="deps_command", required=True)
    for action, text in (
        ("install", "Install dependencies, then check them."),
        ("check", "Check dependencies."),
    ):
        sub = deps_commands.add_parser(action, help=text)
        sub.add_argument("modules", nargs="+", help="Module names (e.g. envs.kind).")

    subparsers.add_parser(
        "doctor", help="Overview of the machine and of the platform (informative, checks nothing)."
    )

    env = subparsers.add_parser(
        "env",
        help="Environments registered by the runner (kept until their destroy succeeds).",
    )
    env_commands = env.add_subparsers(dest="env_command", required=True)
    env_commands.add_parser("list", help="List registered environments.")
    env_clean = env_commands.add_parser(
        "clean", help="Destroy one environment (via its environment module)."
    )
    env_clean.add_argument("environment_id", help="Environment id (see `env list`).")
    env_clean.add_argument("-v", "--verbose", action="store_true", help="Show module output.")
    env_clean_all = env_commands.add_parser(
        "clean-all", help="Destroy all registered environments."
    )
    env_clean_all.add_argument("-v", "--verbose", action="store_true", help="Show module output.")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        load_environment()
    except EnvironmentFileError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    try:
        if args.command == "deps":
            index = discover()
            if args.deps_command == "install":
                install_dependencies(index, args.modules, utils_path())
            else:
                check_dependencies(index, args.modules, utils_path())
            print(f"Dependencies OK: {', '.join(args.modules)}")
            return 0

        if args.command == "doctor":
            run_doctor()
            return 0

        if args.command == "env":
            registry = EnvironmentRegistry()
            entries, broken = registry.scan()
            if args.env_command == "list":
                if not entries and not broken:
                    print("No registered environment.")
                for entry_dir in broken:
                    print(f"{entry_dir.name}  (incomplete entry, removed by the next clean)")
                for entry in entries:
                    print(
                        f"{entry.environment_id}  module={entry.module_path}  "
                        f"registered={entry.registered_at}  run={entry.run_dir}"
                    )
                return 0

            if args.env_command == "clean":
                known = {entry.environment_id for entry in entries} | {d.name for d in broken}
                if args.environment_id not in known:
                    print(
                        f"[ERROR] Unknown environment id: {args.environment_id} (see `env list`).",
                        file=sys.stderr,
                    )
                    return 2
                target = args.environment_id
            else:
                target = None

            destroyed, errors = clean_environments(
                registry=registry, environment_id=target, verbose=args.verbose
            )
            print(f"Environments destroyed: {len(destroyed)}")
            for error in errors:
                print(f"[ERROR] {error}", file=sys.stderr)
            return 1 if errors else 0

        config = load_config(args.config)

        if args.command == "validate":
            prepare_scenario(config)
            print(f"Valid scenario: {config.path}")
            return 0

        if args.command == "run":
            run_dir = run_scenario(
                config,
                verbose=args.verbose,
                quiet=args.quiet,
            )
            print(f"Run completed: {run_dir}")
            return 0

        parser.error(f"Unsupported command: {args.command}")
        return 2

    except ConfigError as exc:
        print(f"[CONFIG ERROR] {exc}", file=sys.stderr)
        return 2
    except ModuleError as exc:
        print(f"[MODULE ERROR] {exc}", file=sys.stderr)
        return 2
    except DiscoveryError as exc:
        print(f"[MODULE ERROR] {exc}", file=sys.stderr)
        return 2
    except DependencyError as exc:
        print(f"[DEPENDENCY ERROR] {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("[INTERRUPTED] Benchmark run interrupted by user.", file=sys.stderr)
        return 130
    except Exception as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

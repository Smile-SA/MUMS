from __future__ import annotations

import argparse
import os
import sys

from benchmark_platform import settings
from benchmark_platform.cleanup import EnvironmentRegistry, clean_environments
from benchmark_platform.config import ConfigError, load_config
from benchmark_platform.dependencies import (
    DependencyError,
    check_dependencies,
    install_dependencies,
)
from benchmark_platform.discovery import DiscoveryError, discover
from benchmark_platform.doctor import run_doctor
from benchmark_platform.modules import ModuleError
from benchmark_platform.runner import prepare_scenario, run_scenario, scenario_modules, utils_path


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
        sub.add_argument("modules", nargs="*", help="Module or util names (e.g. kind).")
        which = sub.add_mutually_exclusive_group()
        which.add_argument(
            "--all", action="store_true", help="Every module and util found (one failure "
            "does not stop the others; all failures are reported at the end)."
        )
        which.add_argument(
            "--scenario", metavar="FILE", help="The modules of a scenario (and their utils)."
        )

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

    config = subparsers.add_parser(
        "config",
        help="Show or change the settings: module_paths, utils_path, env "
        "(configuration file; an environment variable takes precedence).",
    )
    config_commands = config.add_subparsers(dest="config_command")
    config_commands.add_parser("show", help="Each setting, its value and where it comes from.")
    config_commands.add_parser("path", help="The configuration file.")
    config_get = config_commands.add_parser("get", help="The value of one setting.")
    config_get.add_argument("key", choices=list(settings.VARIABLES))
    config_set = config_commands.add_parser("set", help="Write a setting to the file.")
    config_set.add_argument("key", choices=list(settings.VARIABLES))
    config_set.add_argument("values", nargs="+", help="Value (module_paths: one or more).")
    config_unset = config_commands.add_parser("unset", help="Remove a setting from the file.")
    config_unset.add_argument("key", choices=list(settings.VARIABLES))

    exec_parser = subparsers.add_parser(
        "exec",
        help="Run a command in the platform's environment (settings applied), "
        "e.g. benchmark-platform exec -- python3 -m pytest.",
    )
    exec_parser.add_argument("command_line", nargs=argparse.REMAINDER)

    return parser


def _config_command(args: argparse.Namespace) -> int:
    command = args.config_command or "show"
    if command == "path":
        print(settings.config_file())
    elif command == "get":
        value = settings.get(args.key).value
        if value is None:
            return 1
        print(os.pathsep.join(value) if isinstance(value, list) else value)
    elif command == "set":
        path = settings.set_value(args.key, args.values)
        print(f"{args.key} written to {path}")
    elif command == "unset":
        path = settings.unset(args.key)
        print(f"{args.key} removed from {path}")
    else:
        print(f"Configuration file: {settings.config_file()}")
        for key in settings.VARIABLES:
            setting = settings.get(key)
            value = setting.value
            shown = ", ".join(value) if isinstance(value, list) else (value or "-")
            print(f"  {key:<13} {shown}   ({setting.source})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "config":
        try:
            return _config_command(args)
        except settings.SettingsError as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 1

    try:
        settings.apply()
    except settings.SettingsError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1

    if args.command == "exec":
        command = args.command_line[1:] if args.command_line[:1] == ["--"] else args.command_line
        if not command:
            parser.error("exec: give a command, e.g. benchmark-platform exec -- python3 -m pytest")
        try:
            os.execvp(command[0], command)
        except FileNotFoundError:
            print(f"[ERROR] command not found: {command[0]}", file=sys.stderr)
            return 127

    try:
        if args.command == "deps":
            index = discover()
            if sum(bool(x) for x in (args.modules, args.all, args.scenario)) != 1:
                parser.error("deps: give module names, or --all, or --scenario FILE")
            if args.all:
                names = [*sorted(index.modules), *sorted(index.utils)]
            elif args.scenario:
                names = scenario_modules(load_config(args.scenario))
            else:
                names = args.modules
            if args.deps_command == "install":
                install_dependencies(index, names, utils_path(), keep_going=args.all)
            else:
                check_dependencies(index, names, utils_path())
            print(f"Dependencies OK: {', '.join(names)}")
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

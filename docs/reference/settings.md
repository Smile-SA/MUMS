# Settings and installation

## Settings

Three settings tell the platform where things are and in which environment they
run:

| Setting | Variable | Content |
|---|---|---|
| `module_paths` | `BENCHMARK_MODULE_PATHS` | the directories where modules are searched (recursively, for `module.yaml` files) |
| `utils_path` | `BENCHMARK_UTILS_PATH` | the directory of the utils (`util.yaml` files), also given to the modules, which call utils through it |
| `env` | `BENCHMARK_ENV` | a file sourced at the start of every command, e.g. a virtual environment's `bin/activate`: everything the platform runs then goes through it |

Each setting comes from, by priority:

1. **its environment variable**, if set: to override it for one command, a CI, a
   test;
2. **the installation's configuration file**: `<prefix>/benchmark-platform.yaml`,
   where `<prefix>` is the Python environment the platform runs in (its venv), or
   the file named by `BENCHMARK_CONFIG`.

Each installation (each copy of the platform, with its venv) thus has its own
settings: two installations never mix.

In the file, `module_paths` is a list; in the variable, paths are separated by
`:`. An empty element in the variable stands for the file's value: `/mine`
replaces it, `/mine:` adds the file's paths after, `:/mine` before (as `MANPATH`
does).

```yaml
# <venv>/benchmark-platform.yaml
module_paths:
- /home/me/benchmark-platform/modules
utils_path: /home/me/benchmark-platform/utils
env: /home/me/benchmark-platform/.venv/bin/activate
```

The settings are applied once, at the start of every command: the variables are
exported, then `env` is sourced. Everything the platform runs (modules, dependency
scripts, `exec`) sees the result. See `benchmark-platform config` and `exec` in
[cli.md](cli.md).

## `bootstrap.sh`

`benchmark_platform/bootstrap.sh` installs the platform's core (module
dependencies are installed separately, with `benchmark-platform deps install`).

```text
./benchmark_platform/bootstrap.sh [--no-venv] [--venv-dir DIR] [--dev] [--no-shell-profile] [--help]
```

| Option | Effect |
|---|---|
| (none) | installs into a virtual environment, `<repository>/.venv` (created if missing) |
| `--venv-dir DIR` | uses that virtual environment instead (created if missing) |
| `--no-venv` | installs into the active Python environment (at your own risk: the venv avoids interfering with the rest of the machine) |
| `--dev` | also installs the development tools (tests, lint) |
| `--no-shell-profile` | does not touch the shell's profile, only prints what to add |

Environment variable: `PYTHON`, the interpreter used to create the venv (or, with
`--no-venv`, to install into; default: `python3`).

It then:

1. writes the settings to the installation's configuration file (`module_paths`:
   the repository's `modules/`; `utils_path`: its `utils/`; with a venv, `env`:
   the venv's `bin/activate`), keeping any setting already in the file;
2. with a venv, links `~/.local/bin/benchmark-platform` to the venv's command, so
   that it can be called from anywhere without activating anything;
3. adds `~/.local/bin` to `PATH` in the shell's profile (`~/.bashrc`, or `~/.zshrc`
   for zsh), in a marked block, if it is not already there.

Open a new terminal afterwards. Running it again is safe.

## Uninstalling

Delete the venv (it holds the configuration file), the link
`~/.local/bin/benchmark-platform`, and the marked block in the shell's profile
(`# >>> benchmark-platform >>>`). The environments of interrupted runs are listed
by `benchmark-platform env list`: destroy them first.

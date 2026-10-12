# Run directory

Each run gets its own directory, `<output.root_directory>/<name>-<UTC time>-seed<seed>`
(see [scenario.md](scenario.md)), holding everything it produced.

```text
<run>/
├── manifest.yaml           what happened: status, modules, every step
├── data/                   standard data, one directory per format
│   ├── openmetrics/
│   ├── http-requests/
│   ├── run-window/
│   ├── essential-tables/
│   ├── summary/
│   └── ...
├── logs/<module>/          the output of each action (<action>.log), and the module's own logs
├── extras/<module>/        what each module keeps for itself: internal state, debugging
├── provenance/             what produced the results
└── runtime/                the platform's working files (the cluster's kubeconfig)
```

## `manifest.yaml`

Written as the run goes, so that it is up to date even if the run is interrupted.

| Field | Content |
|---|---|
| `run_id`, `scenario`, `seed` | the run's identity |
| `environment_id` | the id of its environment |
| `status` | `running`, then `completed`, `failed` or `interrupted` |
| `error` | the error, if the run failed |
| `started_at`, `ended_at` | UTC times |
| `config` | the copy of the scenario, in `provenance/` |
| `modules` | for each role: the module's name, type, contract, directory, entrypoint |
| `environment` | the environment's module, id and kubeconfig, once created |
| `paths` | the run's directories |
| `events` | one entry per step, in order: its type (`traffic.start`, `run.wait`...), module, call and return times, exit code, status (`completed`, `failed`, `interrupted`), error |

## `data/`

The standard data: see [the formats](../formats/README.md). The platform itself
writes `run-window/`; the modules write the rest.

## `logs/` and `extras/`

One directory per module. `logs/<module>/<action>.log` holds everything the action
printed, whether or not the module asks for a log directory. The rest belongs to
the module: see its README.

## `provenance/`

What produced the results, recorded as it comes (the raw output of standard
commands, files exposed by the system), without selecting or interpreting
anything.

Recorded at the start of the run:

| File | Content |
|---|---|
| `scenario.yaml` | the scenario, as given |
| `platform/commit.txt` | the platform's git commit (`git rev-parse HEAD`) |
| `platform/status.txt` | its uncommitted changes (`git status --porcelain`) |
| `platform/diff.patch` | their content (`git diff HEAD`) |
| `modules.sha256` | a digest of each module and util used (its files, hidden directories and caches excepted), in `sha256sum` format: `<digest>  <name>` |
| `commands.sha256` | a digest of the executable of each command they declare, and of `kubectl`, same format; a command not found appears as a comment |
| `commands/<command>.txt` | the output of `<command> --version` |
| `python-packages.txt` | `python3 -m pip freeze --all`: the Python packages the modules run with, and their versions (for an editable install from a git checkout: its commit) |
| `host/uname.txt` | `uname -a` |
| `host/os-release`, `host/cpuinfo`, `host/meminfo` | copies of `/etc/os-release`, `/proc/cpuinfo`, `/proc/meminfo` |

Recorded at the end of the run's wait, before anything stops (step
`[provenance] collect`), or when the run stops early:

| File | Content |
|---|---|
| `kubernetes/<kind>.yaml` | every kind of object the cluster can list (`kubectl get <kind> -A -o yaml`), except leases, endpoint slices and secrets: the images that ran and their digests, the nodes and their versions, the placement of pods... |
| `kubernetes/events.yaml` | the cluster's events |
| `kubernetes/secrets.txt` | the cluster's Secrets: namespace, name and type only, never their content |

Provenance is best effort: what cannot be recorded leaves its file with the error
instead of the output, and never fails the run.

**A run holds credentials in clear**: `runtime/kubeconfig`. See
[Security](../explanation/concepts.md#security).

## Environments left behind

A run registers its environment before creating it, and unregisters it once it is
destroyed, in `~/.local/state/mums/environments/` (or
`$XDG_STATE_HOME/mums/environments/`). An environment left by an
interrupted run, or kept on purpose, is listed by `mums env list`
and destroyed by `mums env clean`.

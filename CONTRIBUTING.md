# Contributing to benchmark-platform

Thank you for your interest in contributing!

## Getting started

```bash
git clone <repo-url>
cd benchmark-platform
make setup-dev
make check
make lint
make test
```

## Adding a module

The fastest way to contribute is to add a new environment, stack, traffic
generator, observability backend, or optimizer module. Each module is a
self-contained directory with two required files:

- `run.sh` — lifecycle entry point
- `module.yaml` — module descriptor

See [`docs/writing-a-module.md`](docs/writing-a-module.md) for the full contract
and a worked example.

## Submitting changes

1. Fork the repository and create a branch from `main`.
2. Make your changes. Run `make check && make lint && make test` before pushing.
3. Open a pull request. Fill in the PR template.
4. A maintainer will review within a few days.

## Code style

- **Python**: formatted and linted with [Ruff](https://docs.astral.sh/ruff/)
  (`make lint`). Line length 100.
- **Shell**: `bash -n` syntax check via `make check`. Use `set -e` (and
  `set -euo pipefail` in new scripts).
- **Language**: English only in all shipped files.

## Reporting bugs

Use the GitHub issue tracker. Fill in the bug report template with reproduction
steps, expected vs. actual behaviour, and your environment (OS, kind version,
kubectl version).

## License

By contributing you agree that your contributions will be licensed under the
[Apache-2.0 license](LICENSE).

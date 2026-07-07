# Local Setup

## Supported initial use case

The currently supported benchmark path is intended to run locally using:

- Kind for a Kubernetes cluster running in Docker.
- MetalLB for local LoadBalancer exposure.
- Prometheus for metrics collection.
- Online Boutique as the deployed microservice application.
- Locust on the host machine for traffic generation.

This document covers dependency installation and local prerequisite validation only. Deployment/runtime corrections and troubleshooting are documented separately as they are implemented.

## Required system tools

The platform expects the following tools to be installed and available in `PATH`:

```text
bash
curl
docker
git
helm
jq
kind
kubectl
python3
```

Docker must be running and accessible by the current user.

## Create the Python environment

From the repository root:

```bash
make setup
```

This command:

1. Checks required host commands and Docker accessibility.
2. Creates a local Python virtual environment under `.venv/` (recommended for
   isolation, not required — see below).
3. Installs runtime Python dependencies.
4. Validates that runtime imports are available.

Activate the environment when running Python or Locust commands manually:

```bash
source .venv/bin/activate
```

### Skipping the virtual environment

The venv is a convenience, not a hard requirement. If you already manage
your own Python environment, install into it directly:

```bash
CREATE_VENV=false make setup-core
```

`make` targets (`make lint`, `make test`, `make run-basic`, …) fall back to
the active `python3` interpreter automatically when `.venv/` does not exist.

## Development setup

To install development validation tools as well:

```bash
make setup-dev
source .venv/bin/activate
```

## Validate the machine

Run:

```bash
make check-prereqs
make doctor
```

`make check-prereqs` verifies required commands, Docker access and installed runtime Python libraries.

`make doctor` adds local-state diagnostics such as existing Kind clusters and the Kind Docker network when present.

## Syntax checks

Run non-destructive syntax checks:

```bash
make check
```

After installing development dependencies, Ruff can also be run explicitly:

```bash
make lint
```

Existing lint findings may be handled progressively; the core setup validation does not require the whole research prototype to be lint-clean immediately.

## Cleanup

Remove caches without removing datasets or virtual environments:

```bash
make clean
```

Remove only the local Python environment:

```bash
make clean-venv
```

Then recreate it with:

```bash
make setup
```

## Deployment troubleshooting

Standalone environment and frontend-readiness troubleshooting, including Kind/cgroup compatibility and MetalLB endpoint diagnostics, is documented in [`troubleshooting.md`](troubleshooting.md).

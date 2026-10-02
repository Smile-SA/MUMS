SHELL := /bin/bash

# Agnostic of any virtual environment: commands are taken from PATH. Activate a
# venv first if the platform is installed in one (source .venv/bin/activate).
PYTHON    ?= python3
BENCHMARK ?= benchmark-platform
VENV_DIR  ?= .venv
CONFIG    ?= configs/smoke-test.yaml

.PHONY: help \
        setup-core setup-dev setup-module setup-smoke-test \
        check-module install-system-deps-debian \
        check check-shell check-python lint validate-config \
        smoke-test test \
        doctor clean clean-venv clean-env clean-all require-cli

help:
	@echo "Benchmark platform developer commands"
	@echo "(commands are taken from PATH: activate the platform's venv first if it has one)"
	@echo
	@echo "  SETUP"
	@echo "    make setup-core                    Create .venv and install core runtime dependencies"
	@echo "                                       (options: ./benchmark_platform/bootstrap.sh --help)"
	@echo "    make setup-dev                     Core runtime + development dependencies (lint, tests)"
	@echo "    make setup-module MODULE=<name>    Install a module's dependencies, then check them (e.g. envs.kind)"
	@echo "    make setup-smoke-test            Install all modules needed for the smoke test"
	@echo "    make install-system-deps-debian    Install the core system tools (Python, kubectl) on Debian-like systems"
	@echo
	@echo "  QUALITY"
	@echo "    make check-module  MODULE=<name>   Check a module's dependencies"
	@echo "    make check                         Shell and Python syntax checks (non-destructive)"
	@echo "    make lint                          Ruff lint checks (requires make setup-dev)"
	@echo
	@echo "  RUN"
	@echo "    make validate-config [CONFIG=...]  Validate a scenario: config, modules, dependencies"
	@echo "                                       (default: $(CONFIG))"
	@echo "    make smoke-test [ARGS=...]         Short end-to-end run on a real cluster, to check everything works"
	@echo "                                       (ARGS=-v verbose, ARGS=-q quiet)"
	@echo "    make test                          Run Python tests (requires make setup-dev)"
	@echo
	@echo "  MAINTENANCE"
	@echo "    make doctor                        Overview of the machine and of the platform (informative)"
	@echo "    make clean                         Remove Python caches (preserves venv and outputs)"
	@echo "    make clean-venv                    Remove the local Python virtual environment"
	@echo "    make clean-env [ID=...]            Destroy environments left behind by previous runs (all, or one id;"
	@echo "                                       see 'benchmark-platform env list')"
	@echo "    make clean-all                     Remove everything: environments, caches, venv"

# The platform's CLI must be on PATH (installed, and its venv activated if any).
require-cli:
	@command -v $(BENCHMARK) >/dev/null || { echo "$(BENCHMARK) not found on PATH: install the platform" \
		"(make setup-core), and activate its venv if it has one (source $(VENV_DIR)/bin/activate)." >&2; exit 1; }

# --- Setup ---

setup-core:
	./benchmark_platform/bootstrap.sh

setup-dev:
	./benchmark_platform/bootstrap.sh --dev

setup-module: require-cli
	@test -n "$(MODULE)" || (echo "Usage: make setup-module MODULE=traffic.online-boutique" >&2; exit 2)
	$(BENCHMARK) deps install $(MODULE)

# Installs all modules required by configs/smoke-test.yaml.
# Keep in sync with that config if modules change.
setup-smoke-test: setup-core require-cli
	$(BENCHMARK) deps install envs.kind stacks.online-boutique observability.prometheus traffic.online-boutique optimizers.baseline post-processing.essential-tables

check-module: require-cli
	@test -n "$(MODULE)" || (echo "Usage: make check-module MODULE=traffic.online-boutique" >&2; exit 2)
	$(BENCHMARK) deps check $(MODULE)

install-system-deps-debian:
	./benchmark_platform/install_system_deps_debian.sh

# --- Quality ---

check: check-shell check-python

check-shell:
	@echo "=== Checking shell script syntax ==="
	@find . -type f -name '*.sh' \
		-not -path '*/.venv/*' \
		-not -path './utils/helm/chart-repository/*' \
		-print0 | xargs -0 -r -n1 bash -n
	@echo "Shell syntax OK."

check-python:
	@echo "=== Checking Python syntax ==="
	@$(PYTHON) -m compileall -q -x '/\.venv/|chart-repository' \
		benchmark_platform tests modules utils
	@echo "Python syntax OK."

lint:
	$(PYTHON) -m ruff check \
		--exclude utils/helm/chart-repository \
		benchmark_platform tests modules utils

# --- Run ---

validate-config: require-cli
	$(BENCHMARK) validate $(CONFIG)

smoke-test: require-cli
	$(BENCHMARK) run configs/smoke-test.yaml $(ARGS)

test:
	$(PYTHON) -m pytest

# --- Maintenance ---

doctor: require-cli
	$(BENCHMARK) doctor

clean:
	@find . -type d -name '__pycache__' -not -path '*/.venv/*' -prune -exec rm -rf {} +
	@rm -rf .pytest_cache .ruff_cache .coverage htmlcov
	@echo "Removed Python caches. Benchmark outputs and venv preserved."

clean-venv:
	@rm -rf "$(VENV_DIR)"
	@echo "Removed virtual environment: $(VENV_DIR)"

clean-env: require-cli
	$(BENCHMARK) env $(if $(ID),clean $(ID),clean-all)

# clean-env first: it needs the platform CLI, which clean-venv removes.
clean-all: clean-env clean clean-venv

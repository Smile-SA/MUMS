SHELL := /bin/bash

PYTHON    ?= python3
VENV_DIR  ?= .venv
VENV_BIN  := $(VENV_DIR)/bin
# Prefer the venv if it exists (CREATE_VENV=false during setup skips it),
# otherwise fall back to the active interpreter / the CLI on PATH.
VENV_PYTHON := $(shell [ -x "$(VENV_BIN)/python" ] && echo "$(VENV_BIN)/python" || echo "$(PYTHON)")
BENCHMARK := $(shell [ -x "$(VENV_BIN)/benchmark-platform" ] && echo "$(VENV_BIN)/benchmark-platform" || echo benchmark-platform)
CONFIG    ?= configs/basic-online-boutique.yaml

.PHONY: help \
        setup-core setup-dev setup-module setup-basic-online-boutique \
        check-module install-system-deps-debian \
        check check-shell check-python lint validate-config \
        run-basic test smoke \
        clean clean-venv clean-env clean-all

help:
	@echo "Benchmark platform developer commands"
	@echo
	@echo "  SETUP"
	@echo "    make setup-core                    Create .venv and install core runtime dependencies"
	@echo "                                       (CREATE_VENV=false installs into the active Python env)"
	@echo "    make setup-dev                     Core runtime + development dependencies (lint, tests)"
	@echo "    make setup-module MODULE=<name>    Install a module's dependencies, then check them (e.g. envs.kind)"
	@echo "    make setup-basic-online-boutique   Install all modules needed for the basic scenario"
	@echo "    make install-system-deps-debian    Install the core system tools (Python, jq, kubectl) on Debian-like systems"
	@echo
	@echo "  QUALITY"
	@echo "    make check-module  MODULE=<name>   Check a module's dependencies"
	@echo "    make check                         Shell and Python syntax checks (non-destructive)"
	@echo "    make lint                          Ruff lint checks (requires make setup-dev)"
	@echo
	@echo "  RUN"
	@echo "    make validate-config [CONFIG=...]  Validate a scenario: config, modules, dependencies (default: basic-online-boutique)"
	@echo "    make run-basic [ARGS=...]          Run the basic scenario (ARGS=-v verbose, ARGS=-q quiet)"
	@echo "    make test                          Run Python tests (requires make setup-dev)"
	@echo "    make smoke                         End-to-end smoke test on a real cluster (requires Kind)"
	@echo
	@echo "  MAINTENANCE"
	@echo "    make clean                         Remove Python caches (preserves venv and outputs)"
	@echo "    make clean-venv                    Remove the local Python virtual environment"
	@echo "    make clean-env [ID=...]            Destroy environments left behind by previous runs (all, or one id;"
	@echo "                                       see 'benchmark-platform env list')"
	@echo "    make clean-all                     Remove everything: environments, caches, venv"

# --- Setup ---

setup-core:
	./benchmark_platform/bootstrap.sh

setup-dev:
	INSTALL_DEV=true ./benchmark_platform/bootstrap.sh

setup-module:
	@test -n "$(MODULE)" || (echo "Usage: make setup-module MODULE=traffic.online-boutique" >&2; exit 2)
	$(BENCHMARK) deps install $(MODULE)

# Installs all modules required by configs/basic-online-boutique.yaml.
# Keep in sync with that config if modules change.
setup-basic-online-boutique: setup-core
	$(BENCHMARK) deps install envs.kind stacks.online-boutique observability.prometheus traffic.online-boutique optimizers.baseline post-processing.refined-csv

check-module:
	@test -n "$(MODULE)" || (echo "Usage: make check-module MODULE=traffic.online-boutique" >&2; exit 2)
	$(BENCHMARK) deps check $(MODULE)

install-system-deps-debian:
	./benchmark_platform/install_system_deps_debian.sh

# --- Quality ---

check: check-shell check-python

check-shell:
	@echo "=== Checking shell script syntax ==="
	@find . -type f -name '*.sh' \
		-not -path './.venv/*' \
		-not -path './utils/helm/chart-repository/*' \
		-print0 | xargs -0 -r -n1 bash -n
	@echo "Shell syntax OK."

check-python:
	@echo "=== Checking Python syntax ==="
	@$(VENV_PYTHON) -m compileall -q \
		benchmark_platform tests traffic observability utils
	@echo "Python syntax OK."

lint:
	$(VENV_PYTHON) -m ruff check \
		--exclude utils/helm/chart-repository \
		benchmark_platform tests traffic observability utils

# --- Run ---

validate-config:
	$(BENCHMARK) validate $(CONFIG)

run-basic:
	$(BENCHMARK) run configs/basic-online-boutique.yaml $(ARGS)

test:
	$(VENV_PYTHON) -m pytest

smoke:
	./tests/smoke/run_basic_config.sh

# --- Maintenance ---

clean:
	@find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	@rm -rf .pytest_cache .ruff_cache .coverage htmlcov
	@echo "Removed Python caches. Benchmark outputs and venv preserved."

clean-venv:
	@rm -rf "$(VENV_DIR)"
	@echo "Removed virtual environment: $(VENV_DIR)"

clean-env:
	$(BENCHMARK) env $(if $(ID),clean $(ID),clean-all)

# clean-env first: it needs the platform CLI, which clean-venv removes.
clean-all: clean-env clean clean-venv

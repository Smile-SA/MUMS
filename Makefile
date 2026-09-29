SHELL := /bin/bash

PYTHON ?= python3
VENV_DIR ?= .venv
# Prefer the venv if it exists (CREATE_VENV=false during setup skips it),
# otherwise fall back to the active interpreter.
VENV_PYTHON := $(shell [ -x "$(VENV_DIR)/bin/python" ] && echo "$(VENV_DIR)/bin/python" || echo "$(PYTHON)")
# Same for the platform CLI: the venv one if it exists, otherwise the one on PATH.
BENCHMARK_PLATFORM := $(shell [ -x "$(VENV_DIR)/bin/benchmark-platform" ] && echo "$(VENV_DIR)/bin/benchmark-platform" || echo benchmark-platform)

.PHONY: help setup-core setup-dev setup-module check-module install-system-deps-debian check check-shell check-python lint validate-config run-basic test smoke clean clean-venv clean-env

help:
	@echo "Benchmark platform developer commands"
	@echo
	@echo "  make setup-core     Create .venv and install core runtime dependencies"
	@echo "                      (CREATE_VENV=false installs into the active Python environment instead)"
	@echo "  make setup-dev      Create .venv and install core runtime + development dependencies"
	@echo "  make setup-module   Install a module's dependencies, then check them (MODULE=<name>, e.g. envs.kind)"
	@echo "  make check-module   Check a module's dependencies (MODULE=<name>)"
	@echo "  make install-system-deps-debian  Install the core system tools (Python, jq, kubectl) on Debian-like systems (Debian, Ubuntu...)"
	@echo "  make check          Run non-destructive shell and Python syntax checks"
	@echo "  make lint           Run Ruff lint checks (requires make setup-dev)"
	@echo "  make validate-config  Check configuration file format"
	@echo "  make run-basic      Run basic test scenario"
	@echo "                      Pass CLI arguments with ARGS (e.g. ARGS=-v for verbose mode, ARGS=-q for quiet mode)"
	@echo "  make test           Run Python tests when present (requires make setup-dev)"
	@echo "  make smoke          End-to-end smoke test on a real cluster (requires Kind)"
	@echo "  make clean          Remove caches only; preserves virtual env and benchmark outputs"
	@echo "  make clean-venv     Remove the local Python virtual environment"
	@echo "  make clean-env      Destroy environments left behind by previous runs"
	@echo "                      (all of them, or one with ID=<id>; see 'benchmark-platform env list')"

setup-core:
	./benchmark_platform/bootstrap.sh

setup-dev:
	INSTALL_DEV=true ./benchmark_platform/bootstrap.sh

setup-module:
	@test -n "$(MODULE)" || (echo "Usage: make setup-module MODULE=traffic.online-boutique" >&2; exit 2)
	$(BENCHMARK_PLATFORM) deps install $(MODULE)

setup-basic-online-boutique: setup-core
	$(BENCHMARK_PLATFORM) deps install envs.kind stacks.online-boutique observability.prometheus traffic.online-boutique optimizers.baseline post-processing.refined-csv

check-module:
	@test -n "$(MODULE)" || (echo "Usage: make check-module MODULE=traffic.online-boutique" >&2; exit 2)
	$(BENCHMARK_PLATFORM) deps check $(MODULE)

install-system-deps-debian:
	./benchmark_platform/install_system_deps_debian.sh

check: check-shell check-python

check-shell:
	@echo "=== Checking maintained shell script syntax ==="
	@find . -type f -name '*.sh' \
		-not -path './.venv/*' \
		-not -path './utils/helm/chart-repository/*' \
		-print0 | xargs -0 -r -n1 bash -n
	@echo "Shell syntax checks succeeded."

check-python:
	@echo "=== Checking Python syntax ==="
	@$(VENV_PYTHON) -m compileall -q \
		traffic \
		observability \
		utils
	@echo "Python syntax checks succeeded."

lint:
	$(VENV_PYTHON) -m ruff check \
		--exclude utils/helm/chart-repository \
		benchmark_platform tests traffic observability utils

validate-config:
	$(BENCHMARK_PLATFORM) validate configs/basic-online-boutique.yaml

run-basic:
	$(BENCHMARK_PLATFORM) run configs/basic-online-boutique.yaml $(ARGS)

test:
	@if find tests -type f -name 'test_*.py' -print -quit 2>/dev/null | grep -q .; then \
		$(VENV_PYTHON) -m pytest; \
	else \
		echo "No Python tests are committed yet. Dataset and runner tests are added in the testing issue."; \
	fi

smoke:
	./tests/smoke/run_basic_config.sh

clean:
	@find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	@rm -rf .pytest_cache .ruff_cache .coverage htmlcov
	@echo "Removed Python caches and local check artifacts. Benchmark outputs were preserved."

clean-venv:
	@rm -rf "$(VENV_DIR)"
	@echo "Removed virtual environment: $(VENV_DIR)"

clean-env:
	$(BENCHMARK_PLATFORM) env $(if $(ID),clean $(ID),clean-all)

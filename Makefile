SHELL := /bin/bash

PYTHON    ?= python3
VENV_DIR  ?= .venv
VENV_BIN  := $(VENV_DIR)/bin
VENV_PYTHON := $(shell [ -x "$(VENV_BIN)/python" ] && echo "$(VENV_BIN)/python" || echo "$(PYTHON)")
BENCHMARK := $(VENV_BIN)/benchmark-platform
CONFIG    ?= configs/basic-online-boutique.yaml

.PHONY: help \
        setup-core setup-dev setup-module setup-basic-online-boutique \
        check-prereqs check-module doctor install-system-deps-ubuntu \
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
	@echo "    make setup-module MODULE=<path>    Install a single module's dependencies"
	@echo "    make setup-basic-online-boutique   Install all modules needed for the basic scenario"
	@echo "    make install-system-deps-ubuntu    Install Docker, kubectl, kind, Helm and jq (Ubuntu/Debian)"
	@echo
	@echo "  QUALITY"
	@echo "    make check-prereqs                 Validate required system tools and Python runtime imports"
	@echo "    make check-module  MODULE=<path>   Validate tools and Python imports for one module"
	@echo "    make doctor                        System diagnostics: tool versions, Docker state, cgroup"
	@echo "    make check                         Shell and Python syntax checks (non-destructive)"
	@echo "    make lint                          Ruff lint checks (requires make setup-dev)"
	@echo
	@echo "  RUN"
	@echo "    make validate-config [CONFIG=...]  Validate a scenario config (default: basic-online-boutique)"
	@echo "    make run-basic [ARGS=...]          Run the basic scenario (ARGS=-v verbose, ARGS=-q quiet)"
	@echo "    make test                          Run Python tests (requires make setup-dev)"
	@echo "    make smoke                         End-to-end smoke test on a real cluster (requires Kind)"
	@echo
	@echo "  MAINTENANCE"
	@echo "    make clean                         Remove Python caches (preserves venv and outputs)"
	@echo "    make clean-venv                    Remove the local Python virtual environment"
	@echo "    make clean-env [ID=... | SEED=...] Destroy an environment (registry-based; SEED is a legacy alias)"
	@echo "    make clean-all                     Remove everything: caches, venv, and cluster"

# --- Setup ---

setup-core:
	./scripts/bootstrap.sh

setup-dev:
	INSTALL_DEV=true ./scripts/bootstrap.sh

setup-module:
	@test -n "$(MODULE)" || (echo "Usage: make setup-module MODULE=traffic/online-boutique" >&2; exit 2)
	./scripts/install_module_deps.sh "$(MODULE)"

# Installs all modules required by configs/basic-online-boutique.yaml.
# Keep in sync with that config if modules change.
setup-basic-online-boutique: setup-core
	./scripts/install_module_deps.sh envs/kind
	./scripts/install_module_deps.sh stacks/online-boutique
	./scripts/install_module_deps.sh observability/prometheus
	./scripts/install_module_deps.sh observability/analysis
	./scripts/install_module_deps.sh traffic/online-boutique
	./scripts/install_module_deps.sh optimizers/baseline

# --- System prereqs ---

check-prereqs:
	./scripts/check_prereqs.sh --mode all

check-module:
	@test -n "$(MODULE)" || (echo "Usage: make check-module MODULE=traffic/online-boutique" >&2; exit 2)
	./scripts/check_module_deps.sh "$(MODULE)"

doctor:
	./scripts/doctor.sh

install-system-deps-ubuntu:
	./scripts/install_system_deps_ubuntu.sh

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
	$(BENCHMARK) env $(if $(ID),clean $(ID),$(if $(SEED),clean $(SEED),clean-all))

clean-all: clean clean-venv clean-env

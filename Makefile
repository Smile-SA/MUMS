SHELL := /bin/bash

# Agnostic of any virtual environment: the platform's CLI applies its settings
# itself; tools that need its environment run through `mums exec`.
PYTHON    ?= python3
# The platform's CLI: on PATH, or else the link bootstrap.sh creates in ~/.local/bin
# (so that `make setup-smoke-test` works before a new terminal is opened).
MUMS ?= $(or $(shell command -v mums 2>/dev/null),$(wildcard $(HOME)/.local/bin/mums),mums)
VENV_DIR  ?= .venv
CONFIG    ?= configs/smoke-test.yaml

.PHONY: help \
        setup-core setup-dev setup-module setup-smoke-test \
        check-module install-system-deps-debian \
        check check-shell check-python lint validate-config \
        smoke-test test \
        doctor clean clean-venv clean-env clean-all require-cli

help:
	@echo "mums developer commands"
	@echo "(lint and test run in the platform's environment: mums exec)"
	@echo
	@echo "  SETUP"
	@echo "    make setup-core                    Create .venv and install core runtime dependencies"
	@echo "                                       (options: ./mums/bootstrap.sh --help)"
	@echo "    make setup-dev                     Core runtime + development dependencies (lint, tests)"
	@echo "    make setup-module MODULE=<name>    Install a module's dependencies, then check them (e.g. kind)"
	@echo "    make setup-smoke-test              Install all modules needed for the smoke test"
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
	@echo "                                       see 'mums env list')"
	@echo "    make clean-all                     Remove everything: environments, caches, venv"

# The platform's CLI must be on PATH (installed, and its venv activated if any).
require-cli:
	@command -v $(MUMS) >/dev/null || { echo "$(MUMS) not found: install the" \
		"platform (make setup-core), then open a new terminal." >&2; exit 1; }

# --- Setup ---

setup-core:
	./mums/bootstrap.sh

setup-dev:
	./mums/bootstrap.sh --dev

setup-module: require-cli
	@test -n "$(MODULE)" || (echo "Usage: make setup-module MODULE=online-boutique-locust" >&2; exit 2)
	$(MUMS) deps install $(MODULE)

# Installs the dependencies of the modules of the smoke test.
setup-smoke-test: setup-core require-cli
	$(MUMS) deps install --scenario configs/smoke-test.yaml

check-module: require-cli
	@test -n "$(MODULE)" || (echo "Usage: make check-module MODULE=online-boutique-locust" >&2; exit 2)
	$(MUMS) deps check $(MODULE)

install-system-deps-debian:
	./mums/install_system_deps_debian.sh

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
		mums tests modules utils scripts
	@echo "Python syntax OK."

lint: require-cli
	$(MUMS) exec -- $(PYTHON) -m ruff check \
		--config mums/pyproject.toml \
		--exclude utils/helm/chart-repository \
		mums tests modules utils scripts

# --- Run ---

validate-config: require-cli
	$(MUMS) validate $(CONFIG)

smoke-test: require-cli
	$(MUMS) run configs/smoke-test.yaml $(ARGS)

test: require-cli
	$(MUMS) exec -- $(PYTHON) -m pytest

# --- Maintenance ---

doctor: require-cli
	$(MUMS) doctor

clean:
	@find . -type d -name '__pycache__' -not -path '*/.venv/*' -prune -exec rm -rf {} +
	@rm -rf .pytest_cache .ruff_cache .coverage htmlcov
	@echo "Removed Python caches. Benchmark outputs and venv preserved."

clean-venv:
	@rm -rf "$(VENV_DIR)"
	@echo "Removed virtual environment: $(VENV_DIR)"

clean-env: require-cli
	$(MUMS) env $(if $(ID),clean $(ID),clean-all)

# clean-env first: it needs the platform CLI, which clean-venv removes.
clean-all: clean-env clean clean-venv

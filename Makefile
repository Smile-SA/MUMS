SHELL := /bin/bash

PYTHON ?= python3
VENV_DIR ?= .venv
VENV_PYTHON := $(VENV_DIR)/bin/python

.PHONY: help setup-core setup-dev setup-module check-prereqs check-module doctor install-system-deps-ubuntu check check-shell check-python lint validate-config run-basic test smoke clean clean-venv clean-env

help:
	@echo "Benchmark platform developer commands"
	@echo
	@echo "  make setup-core     Create .venv and install core runtime dependencies"
	@echo "  make setup-dev      Create .venv and install core runtime + development dependencies"
	@echo "  make setup-module   Create .venv and install modules dependencies"
	@echo "  make check-prereqs  Validate required system tools and Python runtime imports"
	@echo "  make check-module   Validate required tools and Python imports for modules"
	@echo "  make doctor         Display platform-relevant local diagnostics"
	@echo "  make install-system-deps-ubuntu  Install Docker, kubectl, kind, Helm and jq on Ubuntu/Debian"
	@echo "  make check          Run non-destructive shell and Python syntax checks"
	@echo "  make lint           Run Ruff lint checks (requires make setup-dev)"
	@echo "  make validate-config  Check configuration file format"
	@echo "  make run-basic      Run basic test scenario"
	@echo "  make test           Run Python tests when present (requires make setup-dev)"
	@echo "  make smoke          End-to-end smoke test on a real cluster (requires Kind)"
	@echo "  make clean          Remove caches only; preserves virtual env and benchmark outputs"
	@echo "  make clean-venv     Remove the local Python virtual environment"
	@echo "  make clean-env 	 Remove the benchmark environment"

setup-core:
	./scripts/bootstrap.sh

setup-dev:
	INSTALL_DEV=true ./scripts/bootstrap.sh

setup-module:
	@test -n "$(MODULE)" || (echo "Usage: make setup-module MODULE=traffic/online-boutique" >&2; exit 2)
	./scripts/install_module_deps.sh "$(MODULE)"

setup-basic-online-boutique: setup-core
	./scripts/install_module_deps.sh envs/kind
	./scripts/install_module_deps.sh stacks/online-boutique
	./scripts/install_module_deps.sh observability/prometheus
	./scripts/install_module_deps.sh traffic/online-boutique
	./scripts/install_module_deps.sh optimizers/baseline

check-prereqs:
	./scripts/check_prereqs.sh --mode all

check-module:
	@test -n "$(MODULE)" || (echo "Usage: make check-module MODULE=traffic/online-boutique" >&2; exit 2)
	./scripts/check_module_deps.sh "$(MODULE)"

doctor:
	./scripts/doctor.sh

install-system-deps-ubuntu:
	./scripts/install_system_deps_ubuntu.sh

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
	$(VENV_PYTHON) -m benchmark_platform.cli validate configs/basic-online-boutique.yaml

run-basic:
	$(VENV_PYTHON) -m benchmark_platform.cli run configs/basic-online-boutique.yaml

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
	./scripts/clean_env.sh $(SEED)
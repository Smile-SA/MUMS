SHELL := /bin/bash

PYTHON ?= python3
VENV_DIR ?= .venv
VENV_PYTHON := $(VENV_DIR)/bin/python

.PHONY: help setup setup-dev install install-dev install-system-deps-ubuntu check-prereqs doctor check check-shell check-python lint test clean clean-venv

help:
	@echo "Benchmark platform developer commands"
	@echo
	@echo "  make setup          Create .venv and install runtime dependencies"
	@echo "  make setup-dev      Create .venv and install runtime + development dependencies"
	@echo "  make check-prereqs  Validate required system tools and Python runtime imports"
	@echo "  make doctor         Display platform-relevant local diagnostics"
	@echo "  make install-system-deps-ubuntu  Install Docker, kubectl, kind, Helm and jq on Ubuntu/Debian"
	@echo "  make check          Run non-destructive shell and Python syntax checks"
	@echo "  make lint           Run Ruff lint checks (requires make setup-dev)"
	@echo "  make test           Run Python tests when present (requires make setup-dev)"
	@echo "  make clean          Remove caches only; preserves virtual env and benchmark outputs"
	@echo "  make clean-venv     Remove the local Python virtual environment"

setup:
	./scripts/bootstrap.sh

setup-dev:
	INSTALL_DEV=true ./scripts/bootstrap.sh

check-prereqs:
	./scripts/check_prereqs.sh --mode all

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
	@$(VENV_PYTHON) -m ruff check \
		--exclude utils/helm/chart-repository \
		traffic observability utils

test:
	@if find tests -type f -name 'test_*.py' -print -quit 2>/dev/null | grep -q .; then \
		$(VENV_PYTHON) -m pytest; \
	else \
		echo "No Python tests are committed yet. Dataset and runner tests are added in the testing issue."; \
	fi

clean:
	@find . -type d -name '__pycache__' -prune -exec rm -rf {} +
	@rm -rf .pytest_cache .ruff_cache .coverage htmlcov
	@echo "Removed Python caches and local check artifacts. Benchmark outputs were preserved."

clean-venv:
	@rm -rf "$(VENV_DIR)"
	@echo "Removed virtual environment: $(VENV_DIR)"
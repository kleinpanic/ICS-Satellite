SHELL := /usr/bin/env bash

PYTHON_SYS ?= python3
PYTHON = .venv/bin/python
PIP = .venv/bin/pip
PYTEST_FLAGS ?= -vv --color=yes --durations=10

.PHONY: venv dev install test ci-test lint format build serve doctor smoke seed catalog clean reset-requests

venv:
	$(PYTHON_SYS) -m venv .venv

dev:
	$(PYTHON_SYS) -m venv .venv
	.venv/bin/python -m pip install -U pip
	.venv/bin/python -m pip install -e ".[dev]"

doctor:
	@echo "System Python:"
	@command -v $(PYTHON_SYS) && $(PYTHON_SYS) --version || echo "  $(PYTHON_SYS) not found"
	@echo ""
	@echo "Venv Python:"
	@if [ -f .venv/bin/python ]; then .venv/bin/python --version; else echo "  .venv not created"; fi

install: dev

test:
	@set -euo pipefail; \
	echo "==> Test: ensure venv"; \
	if [ ! -d .venv ]; then \
		$(PYTHON_SYS) -m venv .venv; \
	fi; \
	echo "==> Test: install deps"; \
	.venv/bin/python -m pip install -U pip; \
	.venv/bin/python -m pip install -e ".[dev]"; \
	echo "==> Test: report pytest version"; \
	.venv/bin/python -m pytest --version; \
	echo "==> Test: run pytest"; \
	.venv/bin/python -m pytest $(PYTEST_FLAGS)

ci-test:
	@set -euo; \
	(set -o pipefail) 2>/dev/null && set -o pipefail; \
	cleanup() { \
		status="$$?"; \
		rm -rf .ci-venv; \
		exit "$$status"; \
	}; \
	trap cleanup EXIT; \
	echo "==> CI Test: create ephemeral venv"; \
	$(PYTHON_SYS) -m venv .ci-venv; \
	echo "==> CI Test: install deps"; \
	.ci-venv/bin/python -m pip install -U pip; \
	.ci-venv/bin/python -m pip install -e ".[dev]"; \
	echo "==> CI Test: run pytest"; \
	.ci-venv/bin/python -m pytest $(PYTEST_FLAGS)

lint:
	@test -x $(PYTHON) || (echo "Missing .venv. Run make dev first."; exit 1)
	@echo "==> Lint: ruff check"
	$(PYTHON) -m ruff check .
	@echo "==> Lint: ruff format (check)"
	$(PYTHON) -m ruff format --check .
	@echo "==> Lint: mypy"
	$(PYTHON) -m mypy src

format:
	$(PYTHON) -m ruff format .

clean:
	rm -rf site .pytest_cache state/ephemeris state/tle

build:
	$(PYTHON) -m satpass build --config config/config.yaml --out site/

catalog:
	$(PYTHON) -m satpass catalog build --config config/config.yaml --out site/ --mode stale

serve:
	$(PYTHON) -m http.server --directory site 8000

smoke:
	./scripts/smoke.sh

seed:
	$(PYTHON) -m satpass seed --config config/config.yaml --seed config/seeds/seed_requests.yaml --db data/requests.seed.sqlite --reset

reset-requests:
	$(PYTHON) -m satpass reset-requests --config config/config.yaml --out site/ --yes

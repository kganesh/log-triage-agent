VENV := .venv
PY   := $(VENV)/bin/python

.PHONY: install log test lint run

install:
	python3 -m venv $(VENV)
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet -e ".[dev]"

# Regenerate the sample log. Deterministic, so the tests keep passing.
log:
	$(PY) scripts/make_sample_log.py

test:
	$(VENV)/bin/pytest -q

lint:
	$(VENV)/bin/ruff check src tests scripts
	$(VENV)/bin/ruff format --check src tests scripts

# Needs AWS credentials and Bedrock access. About one cent a run.
run:
	$(VENV)/bin/logtriage sample_logs/checkout-service.log

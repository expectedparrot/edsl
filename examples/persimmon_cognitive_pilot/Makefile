SHELL := /bin/sh
.DEFAULT_GOAL := help

EP_AGENT_ROOT ?= $(abspath ../..)
STUDY_PYTHON := $(EP_AGENT_ROOT)/.venv/bin/python
EP := $(EP_AGENT_ROOT)/.venv/bin/ep

.PHONY: help env-check qa run-pilot

help:
	@printf '%s\n' \
		'make env-check  verify the repository virtual environment' \
		'make qa         validate the pilot persona list' \
		'make run-pilot  run the Persimmon pilot (makes paid API calls)'

env-check:
	@test -f "$(EP_AGENT_ROOT)/pyproject.toml" || { \
		echo "EP_AGENT_ROOT does not contain pyproject.toml: $(EP_AGENT_ROOT)" >&2; \
		exit 1; \
	}
	@test -x "$(STUDY_PYTHON)" || { \
		echo "Repository Python environment is missing: $(STUDY_PYTHON)" >&2; \
		exit 1; \
	}
	@test -x "$(EP)" || { \
		echo "EDSL CLI is missing from the repository environment: $(EP)" >&2; \
		exit 1; \
	}
	@$(STUDY_PYTHON) -c "import edsl, matplotlib, numpy; print('pilot runtime: ok')"

qa: env-check
	$(STUDY_PYTHON) analysis/validate_agent_list.py

run-pilot: env-check
	$(STUDY_PYTHON) run_pilot.py

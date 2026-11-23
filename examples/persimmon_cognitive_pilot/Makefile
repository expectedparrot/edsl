# Portable study Makefile baseline.
#
# Compatibility target: GNU Make 3.81 (the version shipped with macOS).
# Keep one recipe-producing target per script. When a script writes multiple
# files, choose one primary output and make the companion outputs depend on it;
# do not use grouped targets, which require newer GNU Make versions.

SHELL := /bin/sh
.DEFAULT_GOAL := help

# Studies normally live at sessions/topic_<alias>/study_<letter>. Override this
# variable when the study is moved elsewhere.
EP_AGENT_ROOT ?= $(abspath ../../..)
UV_RUN := env -u VIRTUAL_ENV uv run --project $(EP_AGENT_ROOT) --frozen --no-dev --
STUDY_PYTHON := $(UV_RUN) python
EP := $(UV_RUN) ep

.PHONY: help env-check all data edsl-objects tables plots qa report

help:
	@printf '%s\n' \
		'make env-check     verify the locked agent runtime' \
		'make edsl-objects  build saved EDSL objects' \
		'make data          collect or refresh results' \
		'make tables plots  generate analysis outputs' \
		'make qa            run study validators' \
		'make report        compile report deliverables'

env-check:
	@test -f "$(EP_AGENT_ROOT)/pyproject.toml" || { \
		echo "EP_AGENT_ROOT does not contain pyproject.toml: $(EP_AGENT_ROOT)" >&2; \
		exit 1; \
	}
	@$(STUDY_PYTHON) -c "import anthropic, edsl, matplotlib, numpy, pandas; print('agent runtime: ok')"

# Add concrete prerequisites and recipes as the study is implemented. Keep
# these aggregate targets phony; their file prerequisites provide idempotence.
all: report
edsl-objects:
data:
tables:
plots:
qa:
report:

# Portable multi-output pattern:
# writeup/plots/primary.png: analysis/plot_primary.py data/results.ep
# 	$(STUDY_PYTHON) analysis/plot_primary.py
# writeup/plots/companion.png: writeup/plots/primary.png
# 	@test -s $@

# --- Generated AgentList workflow ---
AGENT_SOURCE := data/raw/agents.csv
AGENT_ARTIFACT := data/cooked/agent_list.ep

.PHONY: agent-list qa workflow-setup workflow-verify present

workflow-setup: workflow-gates.json
	@test -n "$(APPROVAL_EVIDENCE)" || { echo "APPROVAL_EVIDENCE is required" >&2; exit 2; }
	$(EP) workflow setup --name "AgentList study" --root . --spec $< --evidence "$(APPROVAL_EVIDENCE)"
	$(EP) workflow gate attest plan-approved --root . --by user --evidence "$(APPROVAL_EVIDENCE)"

agent-list: $(AGENT_ARTIFACT)

$(AGENT_ARTIFACT): $(AGENT_SOURCE)
	@mkdir -p data/cooked
	$(EP) agents create --from-csv $< --name-field name --output $@

qa: $(AGENT_ARTIFACT) data/raw/provenance.json analysis/validate_agent_list.py
	$(STUDY_PYTHON) analysis/validate_agent_list.py

workflow-verify: qa
	$(EP) workflow verify --root .

present: $(AGENT_ARTIFACT)
	$(EP) present $(abspath $<) --title "Validated AgentList"

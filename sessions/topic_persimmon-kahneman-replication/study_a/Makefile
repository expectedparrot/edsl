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
STUDY_PYTHON := $(EP_AGENT_ROOT)/.venv/bin/python
EP := $(EP_AGENT_ROOT)/.venv/bin/ep
PLOT_PYTHON ?= python3

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

# --- Literature-matched, local-inference survey runs ---
RUN_DESCRIPTION := Literature-matched cognitive judgment tasks - Persimmon and GPT-6.2-Sol
REPORT_GROUP_BY ?=
JOB_DIR := edsl_jobs/job_a
AGENTS := $(JOB_DIR)/agent_list.ep
MODELS := $(JOB_DIR)/model_list.ep
SCENARIOS := $(JOB_DIR)/scenario_list.ep

SURVEY_LINDA_A := $(JOB_DIR)/survey_linda_order_a.ep
SURVEY_LINDA_B := $(JOB_DIR)/survey_linda_order_b.ep
SURVEY_ENGINEER := $(JOB_DIR)/survey_engineer_lawyer.ep
SURVEY_BATBALL := $(JOB_DIR)/survey_bat_ball.ep

JOBS_LINDA_A := $(JOB_DIR)/jobs_linda_order_a.ep
JOBS_LINDA_B := $(JOB_DIR)/jobs_linda_order_b.ep
JOBS_ENGINEER := $(JOB_DIR)/jobs_engineer_lawyer.ep
JOBS_BATBALL := $(JOB_DIR)/jobs_bat_ball.ep
JOBS := $(JOBS_LINDA_A) $(JOBS_LINDA_B) $(JOBS_ENGINEER) $(JOBS_BATBALL)

RESULTS_LINDA_A := data/results_linda_order_a.ep
RESULTS_LINDA_B := data/results_linda_order_b.ep
RESULTS_ENGINEER := data/results_engineer_lawyer.ep
RESULTS_BATBALL := data/results_bat_ball.ep
RESULTS_PARTS := $(RESULTS_LINDA_A) $(RESULTS_LINDA_B) $(RESULTS_ENGINEER) $(RESULTS_BATBALL)

.PHONY: prepare post-run complete estimate inspect report-data plots exports costs retry-data workflow-setup workflow-verify report-check present

workflow-setup: workflow-gates.json
	@test -n "$(APPROVAL_EVIDENCE)" || { echo "APPROVAL_EVIDENCE is required" >&2; exit 2; }
	$(EP) workflow setup --name "$(RUN_DESCRIPTION)" --root . --spec $< --evidence "$(APPROVAL_EVIDENCE)"
	$(EP) workflow gate attest plan-approved --root . --by user --evidence "$(APPROVAL_EVIDENCE)"

prepare: workflow-setup edsl-objects estimate

edsl-objects: $(JOBS)

$(SURVEY_LINDA_A): $(JOB_DIR)/study_survey.py
	cd $(JOB_DIR) && $(STUDY_PYTHON) study_survey.py

$(SURVEY_LINDA_B): $(SURVEY_LINDA_A)
	@test -s $@

$(SURVEY_ENGINEER): $(SURVEY_LINDA_A)
	@test -s $@

$(SURVEY_BATBALL): $(SURVEY_LINDA_A)
	@test -s $@

$(AGENTS): $(JOB_DIR)/study_agent_list.py
	cd $(JOB_DIR) && $(STUDY_PYTHON) study_agent_list.py

$(MODELS): $(JOB_DIR)/study_model_list.py
	cd $(JOB_DIR) && $(STUDY_PYTHON) study_model_list.py

$(SCENARIOS): $(JOB_DIR)/study_scenario_list.py
	cd $(JOB_DIR) && $(STUDY_PYTHON) study_scenario_list.py

$(JOBS_LINDA_A): $(SURVEY_LINDA_A) $(AGENTS) $(MODELS)
	$(EP) jobs build --survey $(SURVEY_LINDA_A) --agents $(AGENTS) --models $(MODELS) --output $@

$(JOBS_LINDA_B): $(SURVEY_LINDA_B) $(AGENTS) $(MODELS)
	$(EP) jobs build --survey $(SURVEY_LINDA_B) --agents $(AGENTS) --models $(MODELS) --output $@

$(JOBS_ENGINEER): $(SURVEY_ENGINEER) $(AGENTS) $(MODELS) $(SCENARIOS)
	$(EP) jobs build --survey $(SURVEY_ENGINEER) --agents $(AGENTS) --models $(MODELS) --scenarios $(SCENARIOS) --output $@

$(JOBS_BATBALL): $(SURVEY_BATBALL) $(AGENTS) $(MODELS)
	$(EP) jobs build --survey $(SURVEY_BATBALL) --agents $(AGENTS) --models $(MODELS) --output $@

estimate: $(JOBS)
	$(EP) jobs cost $(JOBS_LINDA_A) --iterations 100 --model gpt-6.2-sol
	$(EP) jobs cost $(JOBS_LINDA_B) --iterations 100 --model gpt-6.2-sol
	$(EP) jobs cost $(JOBS_ENGINEER) --iterations 50 --model gpt-6.2-sol
	$(EP) jobs cost $(JOBS_BATBALL) --iterations 200 --model gpt-6.2-sol
	@echo "Persimmon direct API pricing is not available in the Expected Parrot catalog; its provider charge is unknown."

data: data/results.ep

$(RESULTS_LINDA_A): $(JOBS_LINDA_A)
	@mkdir -p data
	@if test -s "$@"; then echo "Existing results preserved: $@"; else \
		set -a; . "$(EP_AGENT_ROOT)/.env"; set +a; \
		EDSL_SERVICE_RPM_PERSIMMON=30 EDSL_DATABASE_PATH="sqlite:///$(abspath data/edsl_cache.db)" EDSL_SQLLIST_DB_PATH="sqlite:///$(abspath data/sql_list_cache.db)" \
		$(EP) run $(JOBS_LINDA_A) --n 100 --local --max-concurrency 2 --output $@; \
	fi

$(RESULTS_LINDA_B): $(JOBS_LINDA_B)
	@mkdir -p data
	@if test -s "$@"; then echo "Existing results preserved: $@"; else \
		set -a; . "$(EP_AGENT_ROOT)/.env"; set +a; \
		EDSL_SERVICE_RPM_PERSIMMON=30 EDSL_DATABASE_PATH="sqlite:///$(abspath data/edsl_cache.db)" EDSL_SQLLIST_DB_PATH="sqlite:///$(abspath data/sql_list_cache.db)" \
		$(EP) run $(JOBS_LINDA_B) --n 100 --local --max-concurrency 2 --output $@; \
	fi

$(RESULTS_ENGINEER): $(JOBS_ENGINEER)
	@mkdir -p data
	@if test -s "$@"; then echo "Existing results preserved: $@"; else \
		set -a; . "$(EP_AGENT_ROOT)/.env"; set +a; \
		EDSL_SERVICE_RPM_PERSIMMON=30 EDSL_DATABASE_PATH="sqlite:///$(abspath data/edsl_cache.db)" EDSL_SQLLIST_DB_PATH="sqlite:///$(abspath data/sql_list_cache.db)" \
		$(EP) run $(JOBS_ENGINEER) --n 50 --local --max-concurrency 2 --output $@; \
	fi

$(RESULTS_BATBALL): $(JOBS_BATBALL)
	@mkdir -p data
	@if test -s "$@"; then echo "Existing results preserved: $@"; else \
		set -a; . "$(EP_AGENT_ROOT)/.env"; set +a; \
		EDSL_SERVICE_RPM_PERSIMMON=30 EDSL_DATABASE_PATH="sqlite:///$(abspath data/edsl_cache.db)" EDSL_SQLLIST_DB_PATH="sqlite:///$(abspath data/sql_list_cache.db)" \
		$(EP) run $(JOBS_BATBALL) --n 200 --local --max-concurrency 2 --output $@; \
	fi

data/results.ep: $(RESULTS_PARTS) analysis/combine_results.py
	$(STUDY_PYTHON) analysis/combine_results.py $(RESULTS_PARTS) --output $@

data/report-data.json: data/results.ep
	@mkdir -p data
	$(EP) results review data/results.ep $(if $(REPORT_GROUP_BY),--group-by "$(REPORT_GROUP_BY)",) > $@

report-data: data/report-data.json

writeup/tables/results_linda_order_a.csv: $(RESULTS_LINDA_A)
	@mkdir -p writeup/tables
	$(EP) results export $< --column 'model.model' --column 'model.inference_service' --column 'answer.linda_choice' --format csv --output $@

writeup/tables/results_linda_order_b.csv: $(RESULTS_LINDA_B)
	@mkdir -p writeup/tables
	$(EP) results export $< --column 'model.model' --column 'model.inference_service' --column 'answer.linda_choice' --format csv --output $@

writeup/tables/results_engineer_lawyer.csv: $(RESULTS_ENGINEER)
	@mkdir -p writeup/tables
	$(EP) results export $< --column 'model.model' --column 'model.inference_service' --column 'scenario.engineer_count' --column 'scenario.lawyer_count' --column 'scenario.target_occupation' --column 'answer.jack_probability' --column 'answer.dick_probability' --column 'answer.null_probability' --format csv --output $@

writeup/tables/results_bat_ball.csv: $(RESULTS_BATBALL)
	@mkdir -p writeup/tables
	$(EP) results export $< --column 'model.model' --column 'model.inference_service' --column 'answer.bat_ball_answer' --format csv --output $@

plots: writeup/tables/results_linda_order_a.csv writeup/tables/results_linda_order_b.csv writeup/tables/results_engineer_lawyer.csv writeup/tables/results_bat_ball.csv analysis/analyze_study.py
	$(PLOT_PYTHON) analysis/analyze_study.py --linda-a writeup/tables/results_linda_order_a.csv --linda-b writeup/tables/results_linda_order_b.csv --engineer writeup/tables/results_engineer_lawyer.csv --bat-ball writeup/tables/results_bat_ball.csv --output-dir writeup/plots --summary data/study-summary.json

inspect: data/report-data.json
	@cat $<

retry-data: data/results.ep
	@test -n "$(RETRY_REASON)" || { echo "RETRY_REASON is required" >&2; exit 2; }
	@mkdir -p data/attempts
	@attempt=$$(date -u +%Y%m%dT%H%M%SZ); \
		cp data/results.ep data/attempts/$${attempt}-results.ep; \
		printf '%s\n' "$(RETRY_REASON)" > data/attempts/$${attempt}-reason.txt; \
		cp $(RESULTS_PARTS) data/attempts/; \
		rm -f data/results.ep $(RESULTS_PARTS)
	$(MAKE) data
	$(MAKE) costs

costs: data/results.ep
	$(EP) results cost data/results.ep > data/run-costs.json

writeup/tables/results.csv: data/results.ep
	@mkdir -p writeup/tables
	$(EP) results export data/results.ep --column 'agent.*' --column 'model.model' --column 'model.inference_service' --column 'scenario.*' --column 'answer.*' --format csv --output $@

writeup/tables/results.json: data/results.ep
	@mkdir -p writeup/tables
	$(EP) results export data/results.ep --column 'agent.*' --column 'model.model' --column 'model.inference_service' --column 'scenario.*' --column 'answer.*' --format json --output $@

exports: writeup/tables/results.csv writeup/tables/results.json writeup/tables/results_linda_order_a.csv writeup/tables/results_linda_order_b.csv writeup/tables/results_engineer_lawyer.csv writeup/tables/results_bat_ball.csv

tables: exports

qa: analysis/validate_results.py data/results.ep
	$(STUDY_PYTHON) analysis/validate_results.py data/results.ep

post-run: report-data exports costs qa plots

writeup/report.html: writeup/report.md writeup/report.css writeup/tables/results.csv
	cd writeup && pandoc report.md -o report.html --standalone --embed-resources --css=report.css

report: writeup/report.html

report-check: writeup/report.html
	$(EP) report check --root .

workflow-verify: report-check
	$(EP) workflow verify --root .

present: writeup/report.html
	$(EP) present $(abspath $<) --title "$(RUN_DESCRIPTION)"

complete: workflow-verify present

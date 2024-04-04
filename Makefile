###############
# VARIABLES
###############
# Project
GIT_ROOT ?= $(shell git rev-parse --show-toplevel)
PROJECT_NAME ?= $(shell basename $(GIT_ROOT))
# PHONY
.PHONY: help find docs integration docstrings

###############
##@Utils ⭐ 
###############
help: ## Show this helpful message
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[33m%-25s\033[0m %s\n", $$1, $$2} /^##@/ {printf "\n\033[0;32m%s\033[0m\n", substr($$0, 4)} ' $(MAKEFILE_LIST)

find: ## Search for a pattern. Use `make find term="pattern"`
	@find . -type d \( -name '.venv' -o -name '__pycache__' \) -prune -o -type f -print | xargs grep -l "$(term)"

clean: ## Clean temp files
	@echo "Cleaning tempfiles..."
	[ ! -f .coverage ] || rm .coverage
	[ ! -d .mypy_cache ] || rm -rf .mypy_cache
	[ ! -d dist ] || rm -rf dist
	[ ! -f edsl_cache.db ] || rm edsl_cache.db
	[ ! -d htmlcov ] || rm -rf htmlcov
	[ ! -d prof ] || rm -rf prof
	find . -type d -name '.venv' -prune -o -type f -name '*.db' -exec rm -rf {} +
	find . -type d -name '.venv' -prune -o -type f -name '*.log' -exec rm -rf {} +
	find . -type d -name '.venv' -prune -o -type d -name '.pytest_cache' -exec rm -rf {} +
	find . -type d -name '.venv' -prune -o -type d -name '__pycache__' -exec rm -rf {} +

clean-test: ## Clean test files
	[ ! -d dist ] || rm -rf dist
	[ ! -d htmlcov ] || rm -rf htmlcov
	[ ! -d prof ] || rm -rf prof
	[ ! -d tests/temp_outputs ] || rm -rf tests/temp_outputs
	[ ! -f tests/edsl_cache_test.db ] || rm tests/edsl_cache_test.db
	[ ! -f tests/edsl_cache_test.db_temp ] || rm tests/edsl_cache_test.db_temp
	[ ! -f tests/interview.log ] || rm tests/interview.log

clean-all: ## Clean everything (including the venv)
	@if [ -n "$$VIRTUAL_ENV" ]; then \
		echo "Your virtual environment is active. Please deactivate it."; \
		exit 1; \
	fi
	@echo "Cleaning tempfiles..."
	@make clean
	@echo "Cleaning testfiles..."
	@make clean-test
	@echo "Cleaning the venv..."
	@[ ! -d .venv ] || rm -rf .venv
	@echo "Done!"

###############
##@Local Development 💻 🛠️  
###############
install: ## Install all project deps and create a venv (local)
	make clean-all
	@echo "Creating a venv from pyproject.toml and installing deps using poetry..."
	poetry install --with dev
	@echo "All deps installed and venv created."

backup: ## Backup the code to `edsl/.backups/`
	TIMESTAMP=$$(date +"%Y%m%d_%H%M%S"); \
	BACKUP_NAME=$(PROJECT_NAME)_$${TIMESTAMP}.tar.gz; \
	mkdir -p "./.backups"; \
	tar -czf $${BACKUP_NAME} --exclude="*pkl" --exclude="*tar.gz" --exclude="*db" --exclude="*csv" --exclude="./.*" --exclude="node_modules" --exclude="__pycache__" .;\
	mv $${BACKUP_NAME} "./.backups";\
	echo "Backup created: $${BACKUP_NAME}"


docs: ## Generate documentation
	poetry export -f requirements.txt --dev --output docs/requirements.txt
	sphinx-build -b html docs _build

docs-view:
	@UNAME=`uname`; if [ "$$UNAME" = "Darwin" ]; then \
		open _build/index.html; \
	else \
		firefox _build/index.html; \
	fi

format: ## Run code autoformatters (black).
	pre-commit install
	pre-commit run black-jupyter --all-files --all

integration: ## Run integration tests via pytest **consumes API credits**
	## pytest -v -s integration/
	make integration-memory
	make integration-jobs
	make integration-runners
	make integration-questions
	make integration-models
	make integration-visuals
	
integration-memory: ## Run integration tests via pytest **consumes API credits**
	pytest -v integration/test_memory.py

integration-jobs: ## Run integration tests via pytest **consumes API credits**
	pytest -v integration/test_integration_jobs.py

integration-runners: ## Run integration tests via pytest **consumes API credits**
	pytest -v integration/test_runners.py

integration-questions: 
	pytest -v integration/test_questions.py

integration-models: 
	pytest -v integration/test_models.py

integration-job-running:
	pytest -v --log-cli-level=INFO integration/test_job_running.py

integration-tricky-questions:
	pytest -v --log-cli-level=INFO integration/test_tricky_questions.py

integration-visuals:
	cd integration/printing && python check_printing.py

	#pytest --log-cli-level=INFO tests/test_JobRunning.p

lint: ## Run code linters (flake8, pylint, mypy).
	mypy edsl

###############
##@Testing 🐛
###############
test: ## Run regular tests (no server tests) 
	make clean-test
	pytest -xv tests --noserver

test-server: ## Run server tests (no regular tests)
	make clean-test
	pytest -xv tests --server

test-coverage: ## Run regular tests and get a coverage report
	make clean-test
	poetry run coverage run -m pytest tests --ignore=tests/stress && poetry run coverage html
	@UNAME=`uname`; if [ "$$UNAME" = "Darwin" ]; then \
		open htmlcov/index.html; \
	else \
		firefox htmlcov/index.html; \
	fi

test-pypi: ## Build and upload package to test.pypi.com
	make clean-test
	poetry build
	poetry publish -r test-pypi 
	[ ! -d dist ] || rm -rf dist

test-doctests: ## Run doctests
	make clean-test
	pytest --doctest-modules edsl/surveys
	pytest --doctest-modules edsl/agents
	pytest --doctest-modules edsl/scenarios
	pytest --doctest-modules edsl/questions
	pytest --doctest-modules edsl/utilities
	## pytest --doctest-modules edsl/prompts
	## pytest --doctest-modules edsl/reports	
	pytest --doctest-modules edsl/language_models
	pytest --doctest-modules edsl/data


docstrings: 
	pydocstyle edsl

visualize:
	python visualize_structure.py
	@UNAME=`uname`; if [ "$$UNAME" = "Darwin" ]; then \
		open _visualize_structure/index.html; \
	else \
		firefox _visualize_structure/index.html; \
	fi

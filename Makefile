GIT_ROOT ?= $(shell git rev-parse --show-toplevel)
PROJECT_NAME ?= $(shell basename $(GIT_ROOT))
.PHONY: integration


help: ## Show all Makefile targets.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(GIT_ROOT)/Makefile | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[33m%-30s\033[0m %s\n", $$1, $$2}'

backup: ## Backup the code to `edsl/.backups/`
	TIMESTAMP=$$(date +"%Y%m%d_%H%M%S"); \
	BACKUP_NAME=$(PROJECT_NAME)_$${TIMESTAMP}.tar.gz; \
	mkdir -p "./.backups"; \
	tar -czf $${BACKUP_NAME} --exclude="*pkl" --exclude="*tar.gz" --exclude="*db" --exclude="*csv" --exclude="./.*" --exclude="node_modules" --exclude="__pycache__" .;\
	mv $${BACKUP_NAME} "./.backups";\
	echo "Backup created: $${BACKUP_NAME}"

.PHONY: docs 

docs:
	sphinx-build -b html docs _build

docs-view:
	@UNAME=`uname`; if [ "$$UNAME" = "Darwin" ]; then \
		open _build/index.html; \
	else \
		firefox _build/index.html; \
	fi
	
clean: ## Cleans non-essential files and folders
	[ ! -f .coverage ] || rm .coverage
	[ ! -d .mypy_cache ] || rm -rf .mypy_cache
	[ ! -d .venv ] || rm -rf .venv
	[ ! -d dist ] || rm -rf dist
	[ ! -d htmlcov ] || rm -rf htmlcov
	[ ! -d prof ] || rm -rf prof
	[ ! -f edsl_cache.db ] || rm edsl_cache.db
	find . -type d -name '__pycache__' -exec rm -rf {} +
	find . -type d -name '.pytest_cache' -exec rm -rf {} +

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

############
# TESTING
############
testclean:
	[ ! -d dist ] || rm -rf dist
	[ ! -d htmlcov ] || rm -rf htmlcov
	[ ! -d prof ] || rm -rf prof
	[ ! -f tests/edsl_cache_test.db ] || rm tests/edsl_cache_test.db
	[ ! -f tests/edsl_cache_test.db_temp ] || rm tests/edsl_cache_test.db_temp
	[ ! -f tests/interview.log ] || rm tests/interview.log

test: ## Run regular tests (no stress testing) 
	make testclean
	pytest -x tests --ignore=tests/stress

test-coverage: ## Run regular tests and get a coverage report
	make testclean
	poetry run coverage run -m pytest tests --ignore=tests/stress && poetry run coverage html
	@UNAME=`uname`; if [ "$$UNAME" = "Darwin" ]; then \
		open htmlcov/index.html; \
	else \
		firefox htmlcov/index.html; \
	fi

test-stress: ## Run stress tests
	make testclean
	pytest -x tests/stress --profile-svg

test-pypi: ## Build and upload package to test.pypi.com
	make testclean
	poetry build
	poetry publish -r test-pypi 
	[ ! -d dist ] || rm -rf dist

test-doctests: ## Run doctests
	make testclean
	pytest --doctest-modules edsl/surveys
	pytest --doctest-modules edsl/agents
	pytest --doctest-modules edsl/scenarios
	pytest --doctest-modules edsl/questions
	pytest --doctest-modules edsl/utilities
	pytest --doctest-modules edsl/prompts
	pytest --doctest-modules edsl/reports	
	pytest --doctest-modules edsl/language_models

.PHONY: docstrings

docstrings: 
	pydocstyle edsl

visualize:
	python visualize_structure.py
	@UNAME=`uname`; if [ "$$UNAME" = "Darwin" ]; then \
		open _visualize_structure/index.html; \
	else \
		firefox _visualize_structure/index.html; \
	fi


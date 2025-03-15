###############
# VARIABLES
###############
GIT_ROOT ?= $(shell git rev-parse --show-toplevel)
PROJECT_NAME ?= $(shell basename $(GIT_ROOT))
.PHONY: bump docs docstrings find help integration model-report ruff-lint

###############
##@Utils ⭐ 
###############
help: ## Show this helpful message
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[33m%-25s\033[0m %s\n", $$1, $$2} /^##@/ {printf "\n\033[0;32m%s\033[0m\n", substr($$0, 4)} ' $(MAKEFILE_LIST)

install: ## Install all project deps and create a venv (local)
	make clean-all
	@echo "Creating a venv from pyproject.toml and installing deps using poetry..."
	poetry install --with dev
	@echo "All deps installed and venv created."

find: ## Search for a pattern. Use `make find term="pattern"`
	@find . -type d \( -name '.venv' -o -name '__pycache__' \) -prune -o -type f -print | xargs grep -l "$(term)"

clean: ## Clean temp files
	@echo "Cleaning tempfiles..."
	[ ! -f .coverage ] || rm .coverage
	[ ! -d .edsl_cache ] || rm  -rf .edsl_cache
	[ ! -d .mypy_cache ] || rm -rf .mypy_cache
	[ ! -d .temp ] || rm -rf .temp
	[ ! -d dist ] || rm -rf dist
	[ ! -d htmlcov ] || rm -rf htmlcov
	[ ! -f output.html ] || rm output.html
	[ ! -d prof ] || rm -rf prof
	[ ! -f test.dta ] || rm test.dta
	[ ! -f *.docx ] || rm *.docx
	[ ! -f *.html ] || rm *.html
	[ ! -f *.json ] || rm *.json
	find . -type d -name '.venv' -prune -o -type f -name '*.db' -exec rm -rf {} +
	find . -type d -name '.venv' -prune -o -type f -name '*.db.bak' -exec rm -rf {} +
	find . -type d -name '.venv' -prune -o -type f -name '*.log' -exec rm -rf {} +
	find . -type d -name '.venv' -prune -o -type d -name '.pytest_cache' -exec rm -rf {} +
	find . -type d -name '.venv' -prune -o -type d -name '__pycache__' -exec rm -rf {} +

clean-docs: ## Clean documentation files
	[ ! -d .temp/docs ] || rm -rf .temp/docs

clean-test: ## Clean test files
	[ ! -d dist ] || rm -rf dist
	[ ! -d htmlcov ] || rm -rf htmlcov
	[ ! -d prof ] || rm -rf prof
	[ ! -d tests/temp_outputs ] || rm -rf tests/temp_outputs
	[ ! -f tests/edsl_cache_test.db ] || rm tests/edsl_cache_test.db
	[ ! -f tests/interview.log ] || rm tests/interview.log
	[ ! -f tests/test_pytest_report.html ] || rm tests/test_pytest_report.html
	@for file in *.html; do \
		[ ! -f "$$file" ] || rm "$$file"; \
	done
	@for file in *.jsonl; do \
		[ ! -f "$$file" ] || rm "$$file"; \
	done

model-report: ## Generate a model report
	python integration/test_all_questions_and_models.py | tee >> model_report.txt
	echo "Model report generated in model_report.txt"

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

publish: ## Publish the package to PyPI (requires credentials)
	@version=$$(grep "^version =" pyproject.toml | head -1 | sed 's/version = "\(.*\)"/\1/'); \
	echo "You are about to publish EDSL version '$$version' to PyPI."
ifeq ($(force), yes)
	echo "Automatically confirming publish for version '$$version'..."
	poetry build
	poetry publish
else
	@read -p "Are you sure you want to continue? (y/n) " answer; \
	if [ "$$answer" != "y" ]; then \
		echo "Publish canceled."; \
		exit 1; \
	fi
	poetry build
	poetry publish
endif



###############
##@Development 🛠️  
###############
backup: ## Backup the code to `edsl/.backups/`
	TIMESTAMP=$$(date +"%Y%m%d_%H%M%S"); \
	BACKUP_NAME=$(PROJECT_NAME)_$${TIMESTAMP}.tar.gz; \
	mkdir -p "./.backups"; \
	tar -czf $${BACKUP_NAME} --exclude="*pkl" --exclude="*tar.gz" --exclude="*db" --exclude="*csv" --exclude="./.*" --exclude="node_modules" --exclude="__pycache__" .;\
	mv $${BACKUP_NAME} "./.backups";\
	echo "Backup created: $${BACKUP_NAME}"

bump: ## Bump the version of the package
	@python scripts/bump_version.py $(filter-out $@,$(MAKECMDGOALS))
%:
	@:

docs: ## Generate documentation
	make clean-docs
	mkdir -p .temp/docs
	poetry export -f requirements.txt --with dev --output .temp/docs/requirements.txt
	poetry export -f requirements.txt --with dev --output docs/requirements.txt
	sphinx-build -b html docs .temp/docs

docs-view: ## View documentation
	@UNAME=`uname`; if [ "$$UNAME" = "Darwin" ]; then \
		open .temp/docs/index.html; \
	else \
		firefox .temp/docs/index.html; \
	fi

docstrings: ## Check docstrings
	pydocstyle edsl

style-report: ## Check docstrings and generate a report
	python scripts/style_report.py --source edsl --output style_report
	open style_report/index.html

typing-report:
	python scripts/typing_report.py --source edsl --output typing_report
	open typing_report/index.html

format: ## Run code autoformatters (black).
	pre-commit install
	pre-commit run black-jupyter --all-files --all

lint: ## Run code linters (flake8, pylint, mypy).
	mypy edsl

ruff-lint: ## Run ruff linter on all modules in sequence
	poetry run ruff check edsl/instructions
	poetry run ruff check edsl/key_management
	poetry run ruff check edsl/prompts
	poetry run ruff check edsl/tasks
	poetry run ruff check edsl/inference_services
	poetry run ruff check edsl/results
	poetry run ruff check edsl/dataset
	poetry run ruff check edsl/buckets
	poetry run ruff check edsl/interviews
	poetry run ruff check edsl/tokens
	poetry run ruff check edsl/jobs
	poetry run ruff check edsl/surveys
	poetry run ruff check edsl/agents
	poetry run ruff check edsl/scenarios
	poetry run ruff check edsl/questions
	poetry run ruff check edsl/utilities
	poetry run ruff check edsl/language_models
	poetry run ruff check edsl/caching

visualize: ## Visualize the repo structure
	python scripts/visualize_structure.py
	@UNAME=`uname`; if [ "$$UNAME" = "Darwin" ]; then \
		open .temp/visualize_structure/index.html; \
	else \
		firefox .temp/visualize_structure/index.html; \
	fi

###############
##@Testing 🐛
###############
test: ## Run regular tests (no Coop tests) 
	make clean-test
	pytest -xv tests --nocoop

test-token-bucket: ## Run token bucket tests
	make clean-test
	pytest -xv tests --nocoop --token-bucket

test-coop: ## Run Coop tests (no regular tests, requires Coop local server running)
	make clean-test
	pytest -xv tests --coop

test-coverage: ## Run regular tests and get a coverage report
	make clean-test
	poetry run coverage run -m pytest tests --ignore=tests/stress --ignore=tests/coop && poetry run coverage html
	@UNAME=`uname`; if [ "$$UNAME" = "Darwin" ]; then \
		open htmlcov/index.html; \
	else \
		firefox htmlcov/index.html; \
	fi

test-report: ## Run unit tests and view a test report
	make clean-test
	pytest -xv tests --nocoop --html=tests/test_pytest_report.html
	@UNAME=`uname`; if [ "$$UNAME" = "Darwin" ]; then \
		open tests/test_pytest_report.html; \
	else \
		firefox tests/test_pytest_report.html; \
	fi

test-data: ## Create serialization test data for the current EDSL version
	@if echo "$(ARGS)" | grep -q -- --start_new_version; then \
		python scripts/create_serialization_test_data.py $(ARGS); \
	else \
		python scripts/create_serialization_test_data.py; \
	fi
test-doctests: ## Run doctests
	make clean-test
	#pytest --doctest-modules edsl/base.py
	pytest --doctest-modules edsl/instructions
	pytest --doctest-modules edsl/key_management
	pytest --doctest-modules edsl/prompts
	pytest --doctest-modules edsl/tasks
	pytest --doctest-modules edsl/inference_services
	pytest --doctest-modules edsl/results
	pytest --doctest-modules edsl/dataset
	pytest --doctest-modules --ignore=edsl/buckets/token_bucket_client.py edsl/buckets
	pytest --doctest-modules edsl/interviews
	pytest --doctest-modules edsl/tokens
	pytest --doctest-modules edsl/jobs/
	pytest --doctest-modules edsl/surveys
	pytest --doctest-modules edsl/agents
	pytest --doctest-modules edsl/scenarios
	pytest --doctest-modules edsl/questions
	pytest --doctest-modules edsl/utilities
	pytest --doctest-modules edsl/language_models
	pytest --doctest-modules edsl/caching


test-services:
	python integration/test_all_questions_and_models.py

# Directory containing the notebooks
NOTEBOOK_DIR := docs/notebooks

.PHONY: test-notebooks

# Test notebooks
test-notebooks:
	@if [ -z "$(notebook)" ]; then \
		echo "Testing all notebooks..."; \
		pytest -v integration/active/test_notebooks.py; \
	else \
		echo "Testing notebook: $(notebook)"; \
		pytest -v integration/active/test_notebooks.py -k "$(notebook)"; \
	fi

test-starter-tutorial:
	@echo "Testing starter tutorial..."
	pytest -v integration/active/test_notebooks.py -k docs/notebooks/hello_world.ipynb --override-ini config_file=integration/pytest.ini
	pytest -v integration/active/test_notebooks.py -k docs/notebooks/starter_tutorial.ipynb --override-ini config_file=integration/pytest.ini


# .PHONY: test-notebooks	
# test-notebooks: ## Run the notebooks tests
# 	pytest -v integration/active/test_example_notebooks.py

test-integration: ## Run integration tests via pytest **consumes API credits**
	# cd integration/printing && python check_printing.py
	pytest -v integration/active
	# pytest -v integration/test_example_notebooks.py
	pytest -v integration/test_integration_jobs.py
	pytest -v integration/test_memory.py
	pytest -v integration/test_models.py
	pytest -v integration/test_questions.py
	pytest -v integration/test_runners.py
test-serialization: ## Run serialization tests
	pytest -v tests/serialization/test_serialization.py

integration-job-running: # DOES NOT WORK!
	pytest -v --log-cli-level=INFO integration/test_job_running.py

integration-tricky-questions: # DOES NOT WORK!
	pytest -v --log-cli-level=INFO integration/test_tricky_questions.py

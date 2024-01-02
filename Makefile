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

clean: ## Cleans non-essential files and folders
	[ ! -f .coverage ] || rm .coverage
	[ ! -d .mypy_cache ] || rm -rf .mypy_cache
	[ ! -d .venv ] || rm -rf .venv
	[ ! -d htmlcov ] || rm -rf htmlcov
	[ ! -d dist ] || rm -rf dist
	[ ! -f edsl/data/database.db ] || rm edsl/data/database.db
	find . -type d -name '__pycache__' -exec rm -rf {} +
	find . -type d -name '.pytest_cache' -exec rm -rf {} +

coverage: ## Run tests and get a coverage report
	poetry run coverage run -m pytest tests && poetry run coverage html && open htmlcov/index.html

format: ## Run code autoformatters (black).
	pre-commit install
	pre-commit run black-jupyter --all-files --all

integration: ## Run integration tests via pytest **consumes API credits**
	pytest -v -s integration/

lint: ## Run code linters (flake8, pylint, mypy).
	mypy edsl

test: ## Run tests via pytest
	pytest tests

watch-docs: ## Build and watch documentation.
	sphinx-autobuild docs/ docs/_build/html --open-browser --watch $(GIT_ROOT)/edsl/

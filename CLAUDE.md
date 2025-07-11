# EDSL Codebase Reference

## Build & Test Commands
- Install: `make install`
- Run all tests: `make test`
- Run single test: `pytest -xv tests/path/to/test.py`
- Run with coverage: `make test-coverage`
- Run integration tests: `make test-integration`
- Type checking: `make lint` (runs ruff)
- Format code: `make format` (runs black-jupyter)
- Generate docs: `make docs`
- View docs: `make docs-view`

## Code Style Guidelines
- **Formatting**: Use Black for consistent code formatting
- **Imports**: Group by stdlib, third-party, internal modules
- **Type hints**: Required throughout, verified by ruff
- **Naming**: 
  - Classes: PascalCase
  - Methods/functions/variables: snake_case
  - Constants: UPPER_SNAKE_CASE
  - Private items: _prefixed_with_underscore
- **Error handling**: Use custom exception hierarchy with BaseException parent
- **Documentation**: Docstrings for all public functions/classes
- **Testing**: Every feature needs associated tests

## Permissions Guidelines
- **Allowed without asking**: Running tests, linting, code formatting, viewing files
- **Ask before**: Modifying tests, making destructive operations, installing packages
- **Never allowed**: Pushing directly to main branch, changing API keys/secrets

## Module Linting Protocol
When fixing linting issues across the codebase, follow this systematic approach:

### Process
1. **Run auto-fix**: `poetry run ruff check --fix edsl/MODULE_NAME`
2. **Review changes**: Check what was automatically fixed
3. **Manual fixes**: Address remaining issues that require manual intervention
4. **Verify**: Run `poetry run ruff check edsl/MODULE_NAME` to confirm no issues remain
5. **Test**: Run relevant tests to ensure fixes don't break functionality

### Module Priority Order
Fix modules in this order (core dependencies first):
1. **Core/Base modules**: `base/`, `enums.py`, `exceptions.py`
2. **Infrastructure**: `utilities/`, `buckets/`, `caching/`, `key_management/`
3. **Data structures**: `scenarios/`, `agents/`, `questions/`, `surveys/`
4. **Execution**: `language_models/`, `inference_services/`, `jobs/`, `interviews/`
5. **Results/Output**: `results/`, `dataset/`, `prompts/`
6. **Extensions**: `extensions/`, `coop/`, `conversation/`, `plugins/`

### Common Fix Patterns
- **Import issues**: Add missing imports to `TYPE_CHECKING` blocks
- **Type annotations**: Add proper type hints, use `Optional[T]` for nullable types
- **Unused imports**: Remove or move to `TYPE_CHECKING` if only used for typing
- **F-string formatting**: Convert old-style string formatting to f-strings
- **Line length**: Break long lines appropriately

## Module Linting Checklist

### Priority 1: Core/Base Modules
- [x] `base/` - Core base classes and utilities
- [x] `enums.py` - Enumeration definitions
- [ ] `base_exception.py` - Exception hierarchy base

### Priority 2: Infrastructure
- [x] `utilities/` - General utility functions
- [x] `buckets/` - Token bucket management
- [x] `caching/` - Caching infrastructure
- [x] `key_management/` - API key handling

### Priority 3: Data Structures
- [ ] `scenarios/` - Scenario management (IN PROGRESS - some issues remain)
- [x] `agents/` - Agent definitions
- [ ] `questions/` - Question types and validation
- [x] `surveys/` - Survey structure and management

### Priority 4: Execution
- [ ] `language_models/` - Language model interfaces
- [x] `inference_services/` - Service integrations
- [x] `jobs/` - Job execution framework
- [x] `interviews/` - Interview processing

### Priority 5: Results/Output
- [x] `results/` - Result processing
- [x] `dataset/` - Dataset handling
- [x] `prompts/` - Prompt management

### Priority 6: Extensions
- [ ] `extensions/` - Extension system
- [ ] `coop/` - Cooperative features
- [ ] `conversation/` - Conversation management
- [ ] `plugins/` - Plugin system

### Additional Modules
- [x] `instructions/` - Instruction handling
- [ ] `invigilators/` - Invigilator system
- [x] `tasks/` - Task management
- [x] `tokens/` - Token usage tracking
- [ ] `notebooks/` - Jupyter notebook support
- [ ] `display/` - Display utilities
- [ ] `config/` - Configuration management
- [ ] `cli.py` - Command line interface
- [ ] `logger.py` - Logging utilities

### Root Files
- [ ] `__init__.py` - Package initialization
- [ ] `__main__.py` - Main entry point
- [ ] `config.py` - Configuration
- [ ] `data_transfer_models.py` - Data transfer objects
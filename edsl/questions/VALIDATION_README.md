# EDSL Validation Logging System

This system logs validation failures that occur during question answering and provides tools to analyze these failures to improve the "fix" methods for various question types.

## Background

When a language model's response to a question fails validation (e.g., the response doesn't match the expected format or constraints), EDSL throws a `QuestionAnswerValidationError`. To make these validations more robust, we've added a system to log these failures and analyze common patterns.

## Features

- **Validation Logging**: Automatically logs validation failures to a local file
- **Log Analysis**: Tools to analyze validation failures by question type and error message
- **Fix Method Suggestions**: Generates suggestions for improving fix methods based on common failure patterns
- **CLI Interface**: Command-line tools for managing and analyzing validation logs

## Usage

### Command Line Interface

The validation logging system is integrated with the EDSL CLI:

```bash
# Show recent validation failure logs
edsl validation logs

# Show recent logs filtered by question type
edsl validation logs --type QuestionMultipleChoice

# Save logs to a file
edsl validation logs --output validation_logs.json

# Clear all validation logs
edsl validation clear

# Show validation failure statistics
edsl validation stats

# Get suggestions for improving fix methods
edsl validation suggest

# Filter suggestions for a specific question type
edsl validation suggest --type QuestionMultipleChoice

# Generate a comprehensive report
edsl validation report
```

### Programmatic Usage

You can also use the validation logging system programmatically:

```python
from edsl.questions import (
    log_validation_failure,
    get_validation_failure_logs,
    clear_validation_logs,
    get_validation_failure_stats,
    suggest_fix_improvements,
    export_improvements_report
)

# Get recent validation failure logs
logs = get_validation_failure_logs(n=10)

# Get validation failure statistics
stats = get_validation_failure_stats()

# Get suggestions for improving fix methods
suggestions = suggest_fix_improvements()

# Generate a report
report_path = export_improvements_report()
```

## Implementation Details

The validation logging system consists of the following components:

1. **Validation Logger**: Logs validation failures to a local file
2. **Validation Analysis**: Analyzes logs to identify patterns and suggest improvements
3. **CLI Integration**: Provides command-line tools for working with validation logs

### Log Format

Validation failure logs include the following information:

- Timestamp
- Question type and name
- Error message
- Invalid data that failed validation
- Model schema used for validation
- Question details (if available)
- Stack trace

### Storage Location

Logs are stored in the default EDSL log directory:

- Linux/macOS: `~/.edsl/logs/validation_failures.log`
- Windows: `%USERPROFILE%\.edsl\logs\validation_failures.log`

## Future Improvements

Potential future improvements to the validation logging system:

1. Integration with coop for cloud storage and analysis of validation failures
2. Machine learning to automatically suggest fix method improvements
3. Automated tests using common validation failure patterns
4. A web-based dashboard for visualizing validation failure statistics
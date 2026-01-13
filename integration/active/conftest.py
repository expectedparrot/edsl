"""
Pytest configuration for notebook tests.
Captures failures and writes structured error reports for LLM debugging.
"""

import os
import re
import pytest
from pathlib import Path


# Store the error directory path for this test session
_error_session_dir = None


def get_next_error_number(errors_base: Path) -> int:
    """
    Find the next sequential error number based on existing directories.

    Returns 1 if no existing error directories, otherwise max + 1.
    """
    if not errors_base.exists():
        return 1

    # Find all errors_N directories
    pattern = re.compile(r'^errors_(\d+)$')
    max_num = 0

    for item in errors_base.iterdir():
        if item.is_dir():
            match = pattern.match(item.name)
            if match:
                num = int(match.group(1))
                max_num = max(max_num, num)

    return max_num + 1 if max_num > 0 else 1


def get_error_session_dir():
    """Get or create the error directory for this test session."""
    global _error_session_dir
    if _error_session_dir is None:
        # Create notebook_errors directory at project root
        project_root = Path(__file__).parent.parent.parent
        errors_base = project_root / "notebook_errors"
        errors_base.mkdir(exist_ok=True)

        # Create sequentially numbered subdirectory for this run
        next_num = get_next_error_number(errors_base)
        _error_session_dir = errors_base / f"errors_{next_num}"
        _error_session_dir.mkdir(exist_ok=True)

    return _error_session_dir


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Pytest hook to capture test failures and write error reports.
    """
    outcome = yield
    report = outcome.get_result()

    # Only process failures during the "call" phase (actual test execution)
    if report.when == "call" and report.failed:
        # Check if this is a notebook test
        if "notebook_path" in item.funcargs:
            notebook_path = item.funcargs["notebook_path"]
            write_error_report(notebook_path, report)


def write_error_report(notebook_path: str, report):
    """
    Write a structured error report for a failed notebook.

    Args:
        notebook_path: Path to the failed notebook
        report: Pytest report object containing failure info
    """
    error_session_dir = get_error_session_dir()

    # Create directory for this specific notebook
    notebook_name = Path(notebook_path).stem
    notebook_error_dir = error_session_dir / notebook_name
    notebook_error_dir.mkdir(exist_ok=True)

    # Extract error information
    error_message = str(report.longrepr) if report.longrepr else "No error details available"

    # Build the info.md content
    info_content = f"""# Notebook Execution Error

## Notebook Information
- **File**: `{notebook_path}`
- **Absolute Path**: `{os.path.abspath(notebook_path)}`
- **Test**: `{report.nodeid}`

## Error Summary
The notebook failed during execution. See the full traceback below for details.

## Full Traceback
```
{error_message}
```

## Debugging Instructions
1. Open the notebook at the path above
2. Look for the cell that caused the error (indicated in the traceback)
3. Common issues:
   - Missing dependencies or imports
   - API keys or environment variables not set
   - File paths that don't exist
   - Cells that depend on previous cell outputs that weren't executed
4. After fixing, re-run with: `make test-notebooks notebook={notebook_name}`
"""

    # Write the error report
    info_path = notebook_error_dir / "info.md"
    info_path.write_text(info_content)

    print(f"\n[Error Report] Written to: {info_path}")


def pytest_sessionfinish(session, exitstatus):
    """
    Called after the entire test session finishes.
    Cleans up empty error directories if no failures occurred.
    """
    global _error_session_dir
    if _error_session_dir is not None:
        # Check if the directory is empty (no failures)
        if _error_session_dir.exists() and not any(_error_session_dir.iterdir()):
            _error_session_dir.rmdir()
            print(f"\n[Notebook Tests] All tests passed - no error reports generated")
        elif _error_session_dir.exists():
            print(f"\n[Notebook Tests] Error reports written to: {_error_session_dir}")

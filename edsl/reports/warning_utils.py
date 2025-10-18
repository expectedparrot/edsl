"""
Warning utilities for Reports.

This module provides utilities for printing warnings to stderr using rich formatting.
"""

import warnings
from rich.console import Console
from rich.text import Text

# Create a stderr console for warnings
stderr_console = Console(stderr=True, highlight=False)

# Global verbose flag
_VERBOSE = False


def set_verbose(enabled: bool = True) -> None:
    """
    Enable or disable verbose logging.

    When verbose is False (default), only warnings, errors, and success messages are shown.
    When verbose is True, info messages are also shown.

    Args:
        enabled: Whether to enable verbose logging
    """
    global _VERBOSE
    _VERBOSE = enabled


def is_verbose() -> bool:
    """Check if verbose mode is enabled."""
    return _VERBOSE


def print_warning(
    message: str, prefix: str = "WARNING", style: str = "bold yellow"
) -> None:
    """
    Print a warning message to stderr using rich formatting.

    Args:
        message: The warning message to display
        prefix: The prefix to use (default: "WARNING")
        style: The rich style to apply (default: "bold yellow")
    """
    warning_text = Text(f"{prefix}: {message}", style=style)
    stderr_console.print(warning_text)


def print_info(message: str, prefix: str = "INFO", style: str = "bold blue") -> None:
    """
    Print an info message to stderr using rich formatting.

    Only prints if verbose mode is enabled.

    Args:
        message: The info message to display
        prefix: The prefix to use (default: "INFO")
        style: The rich style to apply (default: "bold blue")
    """
    if _VERBOSE:
        info_text = Text(f"{prefix}: {message}", style=style)
        stderr_console.print(info_text)


def print_error(message: str, prefix: str = "ERROR", style: str = "bold red") -> None:
    """
    Print an error message to stderr using rich formatting.

    Args:
        message: The error message to display
        prefix: The prefix to use (default: "ERROR")
        style: The rich style to apply (default: "bold red")
    """
    error_text = Text(f"{prefix}: {message}", style=style)
    stderr_console.print(error_text)


def print_success(
    message: str, prefix: str = "SUCCESS", style: str = "bold green"
) -> None:
    """
    Print a success message to stderr using rich formatting.

    Args:
        message: The success message to display
        prefix: The prefix to use (default: "SUCCESS")
        style: The rich style to apply (default: "bold green")
    """
    success_text = Text(f"{prefix}: {message}", style=style)
    stderr_console.print(success_text)


# Store the original warning handler to avoid recursion
_original_showwarning = warnings.showwarning


def _rich_warning_handler(message, category, filename, lineno, file=None, line=None):
    """
    Custom warning handler that formats warnings using rich and prints to stderr.

    This handler is designed to capture warnings from the edsl package and format them
    with rich styling before printing to stderr.
    """
    # Check if this is from the edsl package
    if "edsl" in filename:
        # Extract just the warning message text
        warning_msg = str(message)

        # Format with rich styling
        formatted_text = Text()
        formatted_text.append("EDSL WARNING: ", style="bold yellow")
        formatted_text.append(warning_msg, style="dim yellow")

        # Print to stderr
        stderr_console.print(formatted_text)
    else:
        # For non-edsl warnings, use the original handler
        _original_showwarning(message, category, filename, lineno, file, line)


def setup_warning_capture():
    """
    Set up the custom warning handler to capture and format edsl warnings.

    This should be called early in the application lifecycle to ensure all
    warnings are captured and formatted properly.
    """
    warnings.showwarning = _rich_warning_handler


def progress_status(message: str):
    """
    Context manager for showing progress status during long operations.

    Shows a spinner with the message. Works well in notebooks.

    Args:
        message: The status message to display

    Example:
        with progress_status("Analyzing themes..."):
            # Long running operation
            result = theme_finder.create_chart()
    """
    from rich.console import Console

    console = Console()
    return console.status(message, spinner="dots")

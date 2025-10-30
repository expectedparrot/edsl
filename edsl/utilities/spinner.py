"""
Spinner utilities for providing visual feedback during long-running operations.

This module provides both context managers and decorators for displaying
spinners in both Jupyter notebooks and terminal environments.
"""

import sys
import time
import threading
from contextlib import contextmanager
from functools import wraps


def is_jupyter():
    """Check if code is running in a Jupyter notebook environment.

    Returns:
        bool: True if running in Jupyter, False otherwise
    """
    try:
        from IPython import get_ipython
        return get_ipython() is not None
    except:
        return False


@contextmanager
def silent_spinner(message="Processing..."):
    """Context manager that displays a spinner while executing code.

    In Jupyter notebooks, displays an italic message that is cleared when done.
    In terminal environments, displays an animated spinner next to the message.

    Args:
        message: The message to display while spinning

    Yields:
        None

    Examples:
        >>> with silent_spinner("Loading data"):  # doctest: +SKIP
        ...     time.sleep(2)
        ...     result = "data loaded"
    """
    if is_jupyter():
        from IPython.display import display, HTML, clear_output
        display(HTML(f'<i>{message}</i>'))
        yield
        clear_output(wait=False)
    else:
        stop_spinner = threading.Event()

        def spin():
            spinner = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
            idx = 0
            while not stop_spinner.is_set():
                sys.stderr.write(f'\r{message} {spinner[idx]}')
                sys.stderr.flush()
                idx = (idx + 1) % len(spinner)
                time.sleep(0.1)
            sys.stderr.write('\r' + ' ' * (len(message) + 2) + '\r')
            sys.stderr.flush()

        spinner_thread = threading.Thread(target=spin)
        spinner_thread.start()
        yield
        stop_spinner.set()
        spinner_thread.join()


def with_spinner(message=None):
    """Decorator that adds a spinner to a function.

    Args:
        message: Optional custom message to display. If not provided,
                uses "Running {function_name}..."

    Returns:
        Decorated function that displays a spinner while executing

    Examples:
        >>> @with_spinner("Loading data")
        ... def load_data():
        ...     time.sleep(3)
        ...     return "Data loaded!"

        >>> @with_spinner()  # Uses default message
        ... def process_data():
        ...     time.sleep(2)
        ...     return "Processing complete!"
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            spinner_message = message or f"Running {func.__name__}..."
            with silent_spinner(spinner_message):
                return func(*args, **kwargs)
        return wrapper
    return decorator

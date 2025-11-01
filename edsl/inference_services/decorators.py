"""
Decorators for inference services.

This module contains decorators that can be applied to inference service methods
to provide common functionality like error reporting, logging, etc.
"""

from functools import wraps
from typing import Callable, Any


def report_errors_async(func: Callable) -> Callable:
    """
    Decorator that automatically reports errors using Coop.report_error()
    before re-raising them. For use with async methods.

    This decorator wraps async methods to catch any exceptions, report them
    to the Coop error reporting system, and then re-raise the original exception.

    Args:
        func: The async function to wrap

    Returns:
        The wrapped async function

    Example:
        @report_errors_async
        async def my_async_method(self):
            # method implementation
            pass
    """

    @wraps(func)
    async def wrapper(*args, **kwargs) -> Any:
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            from ..coop import Coop

            c = Coop()
            await c.report_error(e)
            raise e

    return wrapper


def report_errors_sync(func: Callable) -> Callable:
    """
    Decorator that automatically reports errors using Coop.report_error()
    before re-raising them. For use with synchronous methods.

    This decorator wraps sync methods to catch any exceptions, report them
    to the Coop error reporting system, and then re-raise the original exception.

    Note: This creates a Coop instance synchronously but the report_error method
    is async, so this decorator will need to handle that appropriately.

    Args:
        func: The sync function to wrap

    Returns:
        The wrapped sync function

    Example:
        @report_errors_sync
        def my_sync_method(self):
            # method implementation
            pass
    """

    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # For sync methods, we'll just print the error for now
            # since we can't await the async report_error method
            import sys
            import traceback

            print(
                f"EDSL Error Report (sync): {type(e).__name__}: {str(e)}",
                file=sys.stderr,
            )
            print("Traceback:", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            print("-" * 50, file=sys.stderr)
            raise e

    return wrapper

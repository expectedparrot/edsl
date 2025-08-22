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
    to the Coop error reporting system (if remote_logging is enabled),
    and then re-raise the original exception.

    The remote_logging setting is fetched from /edsl-settings on first use
    and cached in an environment variable to avoid repeated API calls.

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
        import os

        try:
            return await func(*args, **kwargs)
        except Exception as e:
            # Check if remote_logging is enabled
            # First check if we've already fetched and cached the setting
            remote_logging_str = os.environ.get("EDSL_REMOTE_LOGGING")

            if remote_logging_str is None:
                # First time - fetch from /edsl-settings and cache in env var
                try:
                    from ..coop import Coop

                    c = Coop()
                    settings = c.edsl_settings()
                    remote_logging = settings.get("remote_logging", True)
                    # Cache the setting in env var for future use
                    os.environ["EDSL_REMOTE_LOGGING"] = "1" if remote_logging else "0"
                except Exception:
                    # If we can't get settings, default to enabled and cache it
                    os.environ["EDSL_REMOTE_LOGGING"] = "1"
                    remote_logging = True
            else:
                # Use cached value from env var
                remote_logging = remote_logging_str == "1"

            # Report error if enabled
            if remote_logging:
                try:
                    from ..coop import Coop

                    c = Coop()
                    await c.report_error(e)
                except Exception:
                    # If reporting fails, just continue
                    pass

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

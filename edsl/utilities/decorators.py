import functools
import asyncio


def sync_wrapper(async_func):
    """Decorator to create a synchronous wrapper for an asynchronous function."""

    @functools.wraps(async_func)
    def wrapper(*args, **kwargs):
        return asyncio.run(async_func(*args, **kwargs))

    return wrapper

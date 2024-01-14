import functools
import asyncio


def jupyter_nb_handler(func):
    """Decorator to run an async function in the event loop if it's running, or synchronously otherwise."""

    def wrapper(*args, **kwargs):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(func(*args, **kwargs))
        else:
            if loop.is_running():
                return asyncio.ensure_future(func(*args, **kwargs))
            else:
                return asyncio.run(func(*args, **kwargs))

    return wrapper


def sync_wrapper(async_func):
    """Decorator to create a synchronous wrapper for an asynchronous function."""

    @functools.wraps(async_func)
    def wrapper(*args, **kwargs):
        return asyncio.run(async_func(*args, **kwargs))

    return wrapper

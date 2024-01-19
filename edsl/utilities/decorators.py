import functools
import asyncio
import nest_asyncio

nest_asyncio.apply()


def jupyter_nb_handler(func):
    """Decorator to run an async function in the event loop if it's running, or synchronously otherwise."""

    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        # This is an async wrapper to await the coroutine
        return await func(*args, **kwargs)

    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If the loop is running, schedule the coroutine and wait for the result
            future = asyncio.ensure_future(async_wrapper(*args, **kwargs))
            return loop.run_until_complete(future)
        else:
            # If the loop is not running, run the coroutine to completion
            return asyncio.run(async_wrapper(*args, **kwargs))

    return wrapper


def sync_wrapper(async_func):
    """Decorator to create a synchronous wrapper for an asynchronous function."""

    @functools.wraps(async_func)
    def wrapper(*args, **kwargs):
        return asyncio.run(async_func(*args, **kwargs))

    return wrapper

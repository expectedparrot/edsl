import functools
import asyncio
import nest_asyncio

nest_asyncio.apply()

from edsl import __version__ as edsl_version

def add_edsl_version(func):
    """Decorator to add the EDSL version to the return dictionary of a function.
    Meant to be used with "to_dict" methods for serialization.
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        d = func(*args, **kwargs)
        d['edsl_version'] = edsl_version
        class_name = func.__qualname__.split(".")[0]
        d['edsl_class_name'] = class_name
        return d

    return wrapper

def remove_edsl_version(func):
    """Decorator to remove the 'edsl_version' key from the data dictionary"""
    @functools.wraps(func)
    def wrapper(cls, data, *args, **kwargs):
        data_copy = dict(data)
        edsl_version = data_copy.pop('edsl_version', None)
        edsl_classname = data_copy.pop('edsl_class_name', None)
        # TODO: version-specific logic here
        return func(cls, data_copy, *args, **kwargs)
    return wrapper


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

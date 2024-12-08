from functools import wraps
from threading import RLock
import inspect


def synchronized_class(wrapped_class):
    """Class decorator that makes all methods thread-safe."""

    # Add a lock to the class
    setattr(wrapped_class, "_lock", RLock())

    # Get all methods from the class
    for name, method in inspect.getmembers(wrapped_class, inspect.isfunction):
        # Skip magic methods except __getitem__, __setitem__, __delitem__
        if name.startswith("__") and name not in [
            "__getitem__",
            "__setitem__",
            "__delitem__",
        ]:
            continue

        # Create synchronized version of the method
        def create_synchronized_method(method):
            @wraps(method)
            def synchronized_method(*args, **kwargs):
                instance = args[0]  # first arg is self
                with instance._lock:
                    return method(*args, **kwargs)

            return synchronized_method

        # Replace the original method with synchronized version
        setattr(wrapped_class, name, create_synchronized_method(method))

    return wrapped_class

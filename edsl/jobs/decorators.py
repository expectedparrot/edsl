from functools import wraps
from threading import RLock
import inspect
from typing import TypeVar, Callable, cast

try:
    from typing import ParamSpec
except ImportError:
    from typing_extensions import ParamSpec

from ..jobs.data_structures import RunEnvironment, RunParameters, RunConfig


P = ParamSpec("P")
T = TypeVar("T")


def with_config(f: Callable[P, T]) -> Callable[P, T]:
    """
    Decorator that processes function parameters to match the RunConfig dataclass structure.

    This decorator is used primarily with the run() and run_async() methods to provide
    a consistent interface for job configuration while maintaining a clean API.

    The decorator:
    1. Extracts environment-related parameters into a RunEnvironment instance
    2. Extracts execution-related parameters into a RunParameters instance
    3. Combines both into a single RunConfig object
    4. Passes this RunConfig to the decorated function as a keyword argument

    Parameters:
        f (Callable): The function to decorate, typically run() or run_async()

    Returns:
        Callable: A wrapped function that accepts all RunConfig parameters directly

    Example:
        @with_config
        def run(self, *, config: RunConfig) -> Results:
            # Function can now access config.parameters and config.environment
    """
    parameter_fields = {
        name: field.default
        for name, field in RunParameters.__dataclass_fields__.items()
    }
    environment_fields = {
        name: field.default
        for name, field in RunEnvironment.__dataclass_fields__.items()
    }
    # Combined fields dict used for reference during development
    # combined = {**parameter_fields, **environment_fields}

    @wraps(f)
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        environment = RunEnvironment(
            **{k: v for k, v in kwargs.items() if k in environment_fields}
        )
        parameters = RunParameters(
            **{k: v for k, v in kwargs.items() if k in parameter_fields}
        )
        config = RunConfig(environment=environment, parameters=parameters)
        return f(*args, config=config)

    return cast(Callable[P, T], wrapper)


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

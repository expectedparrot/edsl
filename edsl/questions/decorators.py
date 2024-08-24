from typing import Optional, Callable, TypeVar

T = TypeVar("T")


def inject_exception(func: Callable[..., T]) -> Callable[..., T]:
    def wrapper(
        cls, exception_to_throw: Optional[Exception] = None, *args, **kwargs
    ) -> T:
        base_instance = func(cls, *args, **kwargs)
        if exception_to_throw:
            base_instance.exception_to_throw = exception_to_throw
        return base_instance

    return wrapper
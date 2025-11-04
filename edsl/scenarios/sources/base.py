"""
Base classes and utilities for ScenarioList sources.

This module contains the abstract Source base class that all source implementations
inherit from, along with common utilities like the deprecated_classmethod decorator.
"""

from __future__ import annotations
import functools
import warnings
from abc import ABC, abstractmethod
from typing import Callable, Type, TypeVar, TYPE_CHECKING, Any

T = TypeVar("T")


def deprecated_classmethod(
    alternative: str,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator that marks a class method as deprecated.

    Args:
        alternative: The suggested alternative to use instead

    Returns:
        A decorator function that wraps the original method with a deprecation warning
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            warnings.warn(
                f"{func.__qualname__} is deprecated. Use {alternative} instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            return func(*args, **kwargs)

        return wrapper

    return decorator


if TYPE_CHECKING:
    pass


class Source(ABC):
    """
    Abstract base class for all ScenarioList sources.
    
    Each source type should inherit from this class and implement the required methods.
    Sources are automatically registered via the __init_subclass__ hook, making them
    discoverable through the registry.
    """
    
    # Registry to store child classes and their source types
    _registry: dict[str, Type["Source"]] = {}

    def __init_subclass__(cls, **kwargs):
        """Automatically register subclasses with their source_type."""
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "source_type"):
            Source._registry[cls.source_type] = cls

    @classmethod
    @abstractmethod
    def example(cls) -> "Source":
        """
        Return an example instance of this Source type.

        This method should return a valid instance of the Source subclass
        that can be used for testing. The instance should be created with
        reasonable default values that will produce a valid ScenarioList
        when to_scenario_list() is called.

        Returns:
            An instance of the Source subclass
        """
        pass

    @abstractmethod
    def to_scenario_list(self):
        """
        Convert the source to a ScenarioList.

        Returns:
            A ScenarioList containing the data from this source
        """
        pass

    @classmethod
    def get_source_class(cls, source_type: str) -> Type["Source"]:
        """Get the Source subclass for a given source_type."""
        if source_type not in cls._registry:
            raise ValueError(f"No Source subclass found for source_type: {source_type}")
        return cls._registry[source_type]

    @classmethod
    def get_registered_types(cls) -> list[str]:
        """Get a list of all registered source types."""
        return list(cls._registry.keys())

    @classmethod
    def test_all_sources(cls) -> dict[str, bool]:
        """
        Test all registered source types by creating an example instance
        and calling to_scenario_list() on it.

        Returns:
            A dictionary mapping source types to boolean success values
        """
        from ..scenario_list import ScenarioList

        results = {}
        for source_type, source_class in cls._registry.items():
            try:
                # Create example instance
                example_instance = source_class.example()
                # Convert to scenario list
                scenario_list = example_instance.to_scenario_list()
                # Basic validation
                if not isinstance(scenario_list, ScenarioList):
                    results[source_type] = False
                    print(
                        f"Source {source_type} returned {type(scenario_list)} instead of ScenarioList"
                    )
                else:
                    results[source_type] = True
            except Exception as e:
                results[source_type] = False
                print(f"Source {source_type} exception: {e}")
        return results


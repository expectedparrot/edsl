from __future__ import annotations

"""Abstract base class and utilities for EDSL comparison metrics."""

from abc import ABC, abstractmethod
from typing import List, Optional, Any


# Elegant defensive import utility
def optional_import(
    module_name, package_name=None, install_name=None, description=None
):
    """Elegantly handle optional imports with helpful error messages."""
    if package_name is None:
        package_name = module_name
    if install_name is None:
        install_name = package_name
    if description is None:
        description = f"the {package_name} package"

    try:
        return __import__(module_name, fromlist=[""])
    except ImportError:

        class MissingModule:
            def __init__(self, name, install_name, description):
                self.name = name
                self.install_name = install_name
                self.description = description

            def __getattr__(self, item):
                raise ImportError(
                    f"{self.description} is required but not installed. "
                    f"Install with: pip install {self.install_name}"
                )

            def __call__(self, *args, **kwargs):
                raise ImportError(
                    f"{self.description} is required but not installed. "
                    f"Install with: pip install {self.install_name}"
                )

            def __bool__(self):
                return False

        return MissingModule(package_name, install_name, description)


class ComparisonFunction(ABC):
    """Abstract base class for vectorized comparison metrics between answer lists.

    This class defines the interface for all comparison functions in the framework.
    Subclasses must implement the execute method and define a short_name class attribute.

    The design supports vectorized operations where entire lists of answers are compared
    at once, rather than pairwise comparisons, for better performance.

    Attributes:
        short_name (str): A unique identifier for this comparison function.
                         Must be defined by subclasses.

    Examples:
        Creating a custom comparison function:

        >>> class CustomComparison(ComparisonFunction):
        ...     short_name = "custom"
        ...
        ...     def execute(self, answers_A, answers_B, questions=None):
        ...         return [len(a) - len(b) for a, b in zip(answers_A, answers_B)]
        >>>
        >>> comparator = CustomComparison()
        >>> str(comparator)
        'custom'
        >>> comparator.execute(["hello", "world"], ["hi", "earth"])
        [2, -1]

        Subclasses without short_name raise TypeError:

        >>> class BadComparison(ComparisonFunction):
        ...     def execute(self, answers_A, answers_B, questions=None):
        ...         return []
        Traceback (most recent call last):
            ...
        TypeError: BadComparison must define a non-None 'short_name' class attribute

        Serialization and registry:

        >>> exact = ExactMatch()
        >>> data = exact.to_dict()
        >>> data['class_name']
        'ExactMatch'
        >>> restored = ComparisonFunction.from_dict(data)
        >>> isinstance(restored, ExactMatch)
        True
    """

    short_name: str  # subclasses must override with non-None value
    _registry: dict[str, type["ComparisonFunction"]] = {}

    def __init_subclass__(cls, **kwargs):
        """Enforce that subclasses have a non-None short_name and register the class.

        Raises:
            TypeError: If subclass doesn't define short_name or it's None
        """
        super().__init_subclass__(**kwargs)
        if not hasattr(cls, "short_name") or cls.short_name is None:
            raise TypeError(
                f"{cls.__name__} must define a non-None 'short_name' class attribute"
            )
        # Register the class in the registry
        ComparisonFunction._registry[cls.__name__] = cls

    @abstractmethod
    def execute(
        self,
        answers_A: List[str],
        answers_B: List[str],
        questions: List[Any] | None = None,
    ) -> List[Any]:
        """Execute the comparison function on two lists of answers.

        Args:
            answers_A: First list of answers to compare
            answers_B: Second list of answers to compare
            questions: Optional list of question objects for context

        Returns:
            List of comparison scores/results, parallel to the input answer lists.
            The specific type depends on the comparison function implementation.

        Note:
            All three lists must have the same length when provided.
        """
        ...

    def __str__(self) -> str:
        """Return human-readable identifier for this comparison function.

        Returns:
            The short_name of this comparison function.
            Subclasses can override for more detailed representation.
        """
        return self.short_name

    def _get_init_params(self) -> dict[str, Any]:
        """Return the initialization parameters for this instance.

        Subclasses should override this method to return a dictionary of
        parameters that should be passed to __init__ when deserializing.

        Returns:
            Dictionary of parameter names and values needed to reconstruct
            this instance. Default implementation returns an empty dict.

        Examples:
            For a class with no init parameters:

            >>> exact = ExactMatch()
            >>> exact._get_init_params()
            {}

            For a class with init parameters (CosineSimilarity):

            >>> cosine = CosineSimilarity("all-MiniLM-L6-v2")
            >>> cosine._get_init_params()
            {'model_name': 'all-MiniLM-L6-v2'}
        """
        return {}

    def to_dict(self) -> dict[str, Any]:
        """Serialize this comparison function to a dictionary.

        Returns:
            Dictionary with 'class_name' and 'params' keys that can be
            used to reconstruct this instance via from_dict().

        Examples:
            Serialize a simple comparison function:

            >>> exact = ExactMatch()
            >>> data = exact.to_dict()
            >>> data['class_name']
            'ExactMatch'
            >>> data['params']
            {}

            Serialize a parameterized comparison function:

            >>> cosine = CosineSimilarity("all-mpnet-base-v2")
            >>> data = cosine.to_dict()
            >>> data['class_name']
            'CosineSimilarity'
            >>> data['params']['model_name']
            'all-mpnet-base-v2'
        """
        return {
            "class_name": self.__class__.__name__,
            "params": self._get_init_params(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ComparisonFunction":
        """Deserialize a comparison function from a dictionary.

        Args:
            data: Dictionary with 'class_name' and 'params' keys

        Returns:
            New ComparisonFunction instance of the appropriate type

        Raises:
            ValueError: If the class_name is not in the registry

        Examples:
            Deserialize a simple comparison function:

            >>> data = {'class_name': 'ExactMatch', 'params': {}}
            >>> restored = ComparisonFunction.from_dict(data)
            >>> isinstance(restored, ExactMatch)
            True

            Deserialize a parameterized comparison function:

            >>> data = {'class_name': 'CosineSimilarity', 'params': {'model_name': 'all-MiniLM-L6-v2'}}
            >>> restored = ComparisonFunction.from_dict(data)
            >>> isinstance(restored, CosineSimilarity)
            True
            >>> restored.model_name
            'all-MiniLM-L6-v2'

            Round-trip serialization:

            >>> original = JaccardSimilarity()
            >>> restored = ComparisonFunction.from_dict(original.to_dict())
            >>> type(original) == type(restored)
            True
        """
        class_name = data["class_name"]
        params = data.get("params", {})

        if class_name not in cls._registry:
            raise ValueError(
                f"Unknown comparison function class: {class_name}. "
                f"Available classes: {', '.join(cls._registry.keys())}"
            )

        comparison_class = cls._registry[class_name]
        return comparison_class(**params)

"""
EDSL External Service Base Classes.

This module provides the base classes and decorators for creating external services
that extend EDSL types. External services can be exposed as REST APIs and accessed
through the service client infrastructure.

Usage:
    from edsl.services import ExternalService, method_type, MethodType
    from edsl.scenarios import ScenarioList, Scenario

    class MyService(ExternalService):
        service_name = 'my_service'
        extends = [ScenarioList]

        @method_type(MethodType.CLASSMETHOD)
        def fetch_data(self, url: str) -> ScenarioList:
            '''Fetch data from a URL and return as ScenarioList.'''
            # Implementation here
            return ScenarioList.from_list_of_dicts([...])

        @method_type(MethodType.INSTANCE)
        def process(self, instance: ScenarioList) -> ScenarioList:
            '''Process a ScenarioList instance.'''
            # Implementation here
            return instance
"""

from abc import ABC
from typing import Type, Callable, Any, List
from enum import Enum
import inspect
import re
from typing import get_type_hints


class MethodType(Enum):
    """
    Enumeration for different method types in external services.

    - INSTANCE: Methods that operate on an existing instance (takes 'instance' param)
    - CLASSMETHOD: Methods that create new data (no instance required)
    - STATIC: Pure utility methods with no state
    """

    INSTANCE = "instance"
    CLASSMETHOD = "classmethod"
    STATIC = "static"


def method_type(method_type: MethodType) -> Callable:
    """
    Decorator to mark a method's execution type.

    This decorator is required on all public methods of an ExternalService
    to indicate how they should be called by the API.

    Args:
        method_type: The MethodType indicating how this method should be called

    Returns:
        Decorated function with method_type attribute set

    Usage:
        @method_type(MethodType.CLASSMETHOD)
        def scrape(self, url: str) -> ScenarioList:
            ...

        @method_type(MethodType.INSTANCE)
        def transform(self, instance: ScenarioList) -> ScenarioList:
            ...
    """

    def decorator(func: Callable) -> Callable:
        func.method_type = method_type
        return func

    return decorator


class ExternalService(ABC):
    """
    Abstract base class for external services.

    Subclasses must define:
        - service_name: str - A unique identifier for the service
        - extends: List[Type] - List of EDSL types this service extends

    Methods should be decorated with @method_type() to indicate their type.
    The service automatically provides introspection via get_info().

    Example:
        class FirecrawlService(ExternalService):
            service_name = 'firecrawl'
            extends = [ScenarioList]

            @method_type(MethodType.CLASSMETHOD)
            def scrape(self, url: str) -> ScenarioList:
                '''Scrape a webpage and return data.'''
                ...
    """

    service_name: str
    extends: List[Type]

    def __init_subclass__(cls, **kwargs):
        """Validate that subclasses define required class variables."""
        super().__init_subclass__(**kwargs)

        # Check for service_name
        if not hasattr(cls, "service_name") or cls.service_name is None:
            raise TypeError(
                f"ExternalService subclass '{cls.__name__}' must define 'service_name' class variable"
            )

        if not isinstance(cls.service_name, str):
            raise TypeError(
                f"ExternalService subclass '{cls.__name__}': 'service_name' must be a string, "
                f"got {type(cls.service_name).__name__}"
            )

        # Check for extends
        if not hasattr(cls, "extends") or cls.extends is None:
            raise TypeError(
                f"ExternalService subclass '{cls.__name__}' must define 'extends' class variable"
            )

        if not isinstance(cls.extends, (list, tuple)):
            raise TypeError(
                f"ExternalService subclass '{cls.__name__}': 'extends' must be a list of types, "
                f"got {type(cls.extends).__name__}"
            )

    def get_info(self) -> dict:
        """
        Returns information about the service via introspection.

        Returns:
            dict: A dictionary containing:
                - service_name: The service identifier
                - description: Service docstring
                - extends: List of type names this service extends
                - methods: List of method info dicts
        """
        cls = self.__class__

        # Get service name and description from class
        service_name = getattr(cls, "service_name", cls.__name__)
        description = cls.__doc__.strip() if cls.__doc__ else ""

        # Get extends - required field
        if not hasattr(cls, "extends"):
            raise AttributeError(
                f"Class {cls.__name__} is missing required 'extends' attribute"
            )
        extends = [self._get_type_name(t) for t in cls.extends]

        methods = []

        # Get all methods defined in this class (not inherited from ExternalService)
        for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
            # Skip private/dunder methods
            if name.startswith("_"):
                continue

            # Skip methods without the method_type decorator
            if not hasattr(method, "method_type"):
                continue

            # Get method type from our custom decorator
            method_type_value = method.method_type.value

            # Check if method is decorated with @event
            is_event = getattr(method, "_returns_event", False)

            # Parse the docstring
            docstring_info = self._parse_docstring(method.__doc__)

            # Get type hints
            try:
                hints = get_type_hints(method)
            except Exception:
                hints = {}

            # Get return type
            return_type = self._get_type_name(
                hints.get("return", inspect.Parameter.empty)
            )

            # Get parameters
            sig = inspect.signature(method)
            parameters = {}

            for param_name, param in sig.parameters.items():
                if param_name in ("self", "cls"):
                    continue
                if param.kind == inspect.Parameter.VAR_KEYWORD:
                    continue

                param_type = self._get_type_name(
                    hints.get(param_name, param.annotation)
                )
                param_desc = (
                    docstring_info["args"].get(param_name, {}).get("description", "")
                )
                has_default = param.default is not inspect.Parameter.empty

                parameters[param_name] = {
                    "type": param_type,
                    "description": param_desc,
                    "required": not has_default,
                    "default": param.default if has_default else None,
                }

            method_info = {
                "method_name": name,
                "method_type": method_type_value,
                "description": docstring_info["description"],
                "returns": return_type,
                "parameters": parameters,
                "is_event": is_event,
            }

            methods.append(method_info)

        return {
            "service_name": service_name,
            "description": description,
            "extends": extends,
            "methods": methods,
        }

    def _parse_docstring(self, docstring: str) -> dict:
        """Parse a docstring to extract description, args, and returns."""
        if not docstring:
            return {"description": "", "args": {}, "returns": None}

        lines = docstring.strip().split("\n")
        description_lines = []
        args = {}
        returns = None

        current_section = "description"
        current_arg = None

        for line in lines:
            stripped = line.strip()

            if stripped.lower().startswith("args:"):
                current_section = "args"
                continue
            elif stripped.lower().startswith("returns:"):
                current_section = "returns"
                continue

            if current_section == "description":
                if stripped:
                    description_lines.append(stripped)
            elif current_section == "args":
                # Match "param_name: description" or "param_name (type): description"
                arg_match = re.match(r"^(\w+)(?:\s*\(([^)]+)\))?:\s*(.*)$", stripped)
                if arg_match:
                    current_arg = arg_match.group(1)
                    args[current_arg] = {"description": arg_match.group(3).strip()}
                elif current_arg and stripped:
                    # Continuation of previous arg description
                    args[current_arg]["description"] += " " + stripped
            elif current_section == "returns":
                # Match "Type: description" or just description
                return_match = re.match(r"^(\w+):\s*(.*)$", stripped)
                if return_match:
                    returns = return_match.group(2).strip()
                elif stripped:
                    returns = stripped

        return {
            "description": " ".join(description_lines),
            "args": args,
            "returns": returns,
        }

    def _get_type_name(self, annotation) -> str:
        """Get a string representation of a type annotation."""
        if annotation is inspect.Parameter.empty:
            return "Any"
        if hasattr(annotation, "__name__"):
            return annotation.__name__
        return str(annotation).replace("typing.", "")

    def _to_serializable(self, obj: Any) -> Any:
        """Recursively convert an object to JSON-serializable types."""
        if obj is None:
            return None
        elif isinstance(obj, (str, int, float, bool)):
            return obj
        elif isinstance(obj, dict):
            return {k: self._to_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._to_serializable(item) for item in obj]
        elif hasattr(obj, "to_dict"):
            return obj.to_dict()
        elif hasattr(obj, "__dict__"):
            # Convert object with __dict__ (like DocumentMetadata)
            return {
                k: self._to_serializable(v)
                for k, v in obj.__dict__.items()
                if not k.startswith("_")
            }
        elif hasattr(obj, "model_dump"):
            # Pydantic models
            return obj.model_dump()
        elif hasattr(obj, "dict"):
            # Older pydantic models
            return obj.dict()
        else:
            # Fallback to string
            return str(obj)

"""
Vibes Registry Metaclass

Provides a registry system for vibes methods similar to the question registry pattern.
Enables automatic registration of vibes handlers for dynamic dispatch and remote execution.
"""

from __future__ import annotations
from abc import ABCMeta
from typing import Dict, Type, Any, Optional, Callable
import inspect


class RegisterVibesMethodsMeta(ABCMeta):
    """
    Metaclass for registering vibes methods for remote dispatch.

    Similar to RegisterQuestionsMeta but designed for method-level registration
    rather than class-level. Enables automatic registration of vibes methods
    for remote execution via a generic dispatch system.

    Registry Structure:
    {
        "survey": {
            "from_vibes": {
                "handler_class": SurveyGenerator,
                "handler_function": generate_survey_from_vibes,
                "request_schema": FromVibesRequest,
                "response_schema": SurveySchema,
                "is_classmethod": True,
                "metadata": {...}
            },
            "vibe_edit": {...},
            ...
        }
    }
    """

    _registry: Dict[str, Dict[str, Any]] = {}

    def __init__(cls, name, bases, dct):
        """
        Initialize the class and register it if it defines vibes method metadata.

        Classes must define these attributes to be registered:
        - vibes_target: str (e.g., "survey", "agent", "question")
        - vibes_method: str (e.g., "from_vibes", "vibe_edit")
        - handler_class: type (e.g., SurveyGenerator)
        - handler_function: callable (e.g., generate_survey_from_vibes)
        - request_schema: type (Pydantic model)
        - response_schema: type (Pydantic model)

        Optional attributes:
        - is_classmethod: bool (default False)
        - metadata: dict (additional information)
        """
        super().__init__(name, bases, dct)

        # Only register non-base classes that define vibes metadata
        if name not in ["VibesHandlerBase", "VibesMethodBase"]:
            # Check if this class defines vibes method registration
            if hasattr(cls, "vibes_target") and hasattr(cls, "vibes_method"):
                target = cls.vibes_target
                method = cls.vibes_method

                # Validate required attributes
                required_attrs = [
                    "handler_class",
                    "handler_function",
                    "request_schema",
                    "response_schema",
                ]

                missing_attrs = []
                for attr in required_attrs:
                    if not hasattr(cls, attr):
                        missing_attrs.append(attr)

                if missing_attrs:
                    raise AttributeError(
                        f"Vibes handler {name} must define these attributes: {missing_attrs}. "
                        f"Missing: {', '.join(missing_attrs)}"
                    )

                # Validate handler_function signature
                handler_func = cls.handler_function
                if not callable(handler_func):
                    raise TypeError(
                        f"handler_function must be callable, got {type(handler_func)} for {name}"
                    )

                # Validate schemas are classes (should be Pydantic models)
                for schema_attr in ["request_schema", "response_schema"]:
                    schema_cls = getattr(cls, schema_attr)
                    if not inspect.isclass(schema_cls):
                        raise TypeError(
                            f"{schema_attr} must be a class (Pydantic model), got {type(schema_cls)} for {name}"
                        )

                # Initialize target in registry if not exists
                if target not in cls._registry:
                    cls._registry[target] = {}

                # Check for duplicate registration
                if method in cls._registry[target]:
                    existing_handler = cls._registry[target][method].get(
                        "handler_class", "Unknown"
                    )
                    raise ValueError(
                        f"Duplicate registration for {target}.{method}. "
                        f"Already registered by {existing_handler}, attempted by {name}"
                    )

                # Register the method handler
                cls._registry[target][method] = {
                    "handler_class": cls.handler_class,
                    "handler_function": cls.handler_function,
                    "request_schema": cls.request_schema,
                    "response_schema": cls.response_schema,
                    "is_classmethod": getattr(cls, "is_classmethod", False),
                    "metadata": getattr(cls, "metadata", {}),
                    "registered_by": name,
                }

                # Store reverse mapping for debugging
                if not hasattr(cls, "_reverse_registry"):
                    cls._reverse_registry = {}
                cls._reverse_registry[name] = (target, method)

    @classmethod
    def get_registry(cls) -> Dict[str, Dict[str, Any]]:
        """
        Return the complete registry.

        Returns:
            dict: Complete registry mapping targets to methods to handler info
        """
        return cls._registry.copy()

    @classmethod
    def get_method_handler(cls, target: str, method: str) -> Optional[Dict[str, Any]]:
        """
        Get handler information for a specific target and method.

        Args:
            target: Target object type (e.g., "survey", "agent")
            method: Method name (e.g., "from_vibes", "vibe_edit")

        Returns:
            dict or None: Handler information if found, None otherwise
        """
        return cls._registry.get(target, {}).get(method)

    @classmethod
    def list_available_methods(cls, target: str) -> list[str]:
        """
        List all registered methods for a target.

        Args:
            target: Target object type (e.g., "survey", "agent")

        Returns:
            list: List of method names available for the target
        """
        return list(cls._registry.get(target, {}).keys())

    @classmethod
    def list_available_targets(cls) -> list[str]:
        """
        List all registered targets.

        Returns:
            list: List of target object types with registered methods
        """
        return list(cls._registry.keys())

    @classmethod
    def is_method_registered(cls, target: str, method: str) -> bool:
        """
        Check if a method is registered for a target.

        Args:
            target: Target object type (e.g., "survey", "agent")
            method: Method name (e.g., "from_vibes", "vibe_edit")

        Returns:
            bool: True if method is registered, False otherwise
        """
        return cls.get_method_handler(target, method) is not None

    @classmethod
    def get_handler_function(cls, target: str, method: str) -> Optional[Callable]:
        """
        Get the handler function for a specific target and method.

        Args:
            target: Target object type (e.g., "survey", "agent")
            method: Method name (e.g., "from_vibes", "vibe_edit")

        Returns:
            callable or None: Handler function if found, None otherwise
        """
        handler_info = cls.get_method_handler(target, method)
        return handler_info["handler_function"] if handler_info else None

    @classmethod
    def get_request_schema(cls, target: str, method: str) -> Optional[Type]:
        """
        Get the request schema class for a specific target and method.

        Args:
            target: Target object type (e.g., "survey", "agent")
            method: Method name (e.g., "from_vibes", "vibe_edit")

        Returns:
            type or None: Request schema class if found, None otherwise
        """
        handler_info = cls.get_method_handler(target, method)
        return handler_info["request_schema"] if handler_info else None

    @classmethod
    def get_response_schema(cls, target: str, method: str) -> Optional[Type]:
        """
        Get the response schema class for a specific target and method.

        Args:
            target: Target object type (e.g., "survey", "agent")
            method: Method name (e.g., "from_vibes", "vibe_edit")

        Returns:
            type or None: Response schema class if found, None otherwise
        """
        handler_info = cls.get_method_handler(target, method)
        return handler_info["response_schema"] if handler_info else None

    @classmethod
    def validate_request(cls, target: str, method: str, **kwargs) -> Any:
        """
        Validate request parameters using the registered schema.

        Args:
            target: Target object type (e.g., "survey", "agent")
            method: Method name (e.g., "from_vibes", "vibe_edit")
            **kwargs: Request parameters to validate

        Returns:
            Pydantic model instance: Validated request object

        Raises:
            ValueError: If method not registered
            ValidationError: If request parameters invalid
        """
        request_schema = cls.get_request_schema(target, method)
        if not request_schema:
            raise ValueError(f"No handler registered for {target}.{method}")

        return request_schema(**kwargs)

    @classmethod
    def validate_response(cls, target: str, method: str, response_data: Any) -> Any:
        """
        Validate response data using the registered schema.

        Args:
            target: Target object type (e.g., "survey", "agent")
            method: Method name (e.g., "from_vibes", "vibe_edit")
            response_data: Response data to validate (dict or model instance)

        Returns:
            Pydantic model instance: Validated response object

        Raises:
            ValueError: If method not registered
            ValidationError: If response data invalid
        """
        response_schema = cls.get_response_schema(target, method)
        if not response_schema:
            raise ValueError(f"No handler registered for {target}.{method}")

        if isinstance(response_data, response_schema):
            return response_data
        else:
            return response_schema(**response_data)

    @classmethod
    def debug_registry(cls) -> str:
        """
        Return a formatted string representation of the registry for debugging.

        Returns:
            str: Human-readable registry contents
        """
        if not cls._registry:
            return "Registry is empty"

        lines = ["Vibes Method Registry:"]
        for target, methods in cls._registry.items():
            lines.append(f"  {target}:")
            for method, info in methods.items():
                registered_by = info.get("registered_by", "Unknown")
                handler_func = info.get("handler_function", {})
                handler_name = getattr(handler_func, "__name__", "Unknown")
                is_classmethod = info.get("is_classmethod", False)
                method_type = "classmethod" if is_classmethod else "instance method"

                lines.append(f"    {method} ({method_type}):")
                lines.append(f"      Registered by: {registered_by}")
                lines.append(f"      Handler function: {handler_name}")
                lines.append(f"      Handler class: {info.get('handler_class', {})}")
                lines.append(f"      Request schema: {info.get('request_schema', {})}")
                lines.append(
                    f"      Response schema: {info.get('response_schema', {})}"
                )

        return "\n".join(lines)


if __name__ == "__main__":
    # Example usage and testing
    print("Vibes Registry System")
    print("=" * 50)

    # Print current registry state
    print(RegisterVibesMethodsMeta.debug_registry())

    # Test utility methods
    print(f"\nAvailable targets: {RegisterVibesMethodsMeta.list_available_targets()}")

    for target in RegisterVibesMethodsMeta.list_available_targets():
        methods = RegisterVibesMethodsMeta.list_available_methods(target)
        print(f"Methods for {target}: {methods}")

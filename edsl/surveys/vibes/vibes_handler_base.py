"""
Vibes Handler Base Class

Provides the base class for vibes method handler registrations.
All vibes handler classes should inherit from VibesHandlerBase to
automatically register their methods in the vibes registry.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, Type, Optional
from pydantic import BaseModel

try:
    from .vibes_registry import RegisterVibesMethodsMeta
except ImportError:
    from vibes_registry import RegisterVibesMethodsMeta


class VibesHandlerBase(ABC, metaclass=RegisterVibesMethodsMeta):
    """
    Base class for vibes method handlers.

    Subclasses must define these class attributes to register a vibes method:

    Required attributes:
        vibes_target: str           # Target object type (e.g., "survey", "agent", "question")
        vibes_method: str           # Method name (e.g., "from_vibes", "vibe_edit")
        handler_class: Type         # Handler class (e.g., SurveyGenerator, VibeEdit)
        handler_function: Callable  # Handler function (e.g., generate_survey_from_vibes)
        request_schema: Type[BaseModel]   # Pydantic request schema
        response_schema: Type[BaseModel]  # Pydantic response schema

    Optional attributes:
        is_classmethod: bool = False      # True for classmethods like from_vibes
        metadata: Dict[str, Any] = {}     # Additional handler metadata

    Example:
        class FromVibesHandler(VibesHandlerBase):
            vibes_target = "survey"
            vibes_method = "from_vibes"
            handler_class = SurveyGenerator
            handler_function = generate_survey_from_vibes
            request_schema = FromVibesRequest
            response_schema = SurveySchema
            is_classmethod = True

            @classmethod
            def execute_local(cls, survey_cls, **kwargs):
                return cls.handler_function(survey_cls, **kwargs)

    The metaclass RegisterVibesMethodsMeta automatically registers all
    subclasses in the global vibes registry for dispatch and remote execution.
    """

    # These must be defined by subclasses
    vibes_target: str
    vibes_method: str
    handler_class: Type
    handler_function: callable
    request_schema: Type[BaseModel]
    response_schema: Type[BaseModel]
    is_classmethod: bool = False
    metadata: Dict[str, Any] = {}

    @classmethod
    @abstractmethod
    def execute_local(cls, **kwargs) -> Any:
        """
        Execute the vibes method locally.

        This method should call the appropriate handler function with
        the provided arguments and return the result.

        Args:
            **kwargs: Method-specific arguments

        Returns:
            Any: Method execution result (typically Survey, Agent, etc.)

        Example:
            @classmethod
            def execute_local(cls, survey_cls, description: str, **kwargs):
                return cls.handler_function(survey_cls, description, **kwargs)
        """
        pass

    @classmethod
    def to_remote_request(cls, **kwargs) -> Dict[str, Any]:
        """
        Convert local method arguments to remote request format.

        Validates the arguments using the request schema and returns
        a dictionary suitable for sending to a remote server.

        Args:
            **kwargs: Local method arguments

        Returns:
            dict: Validated request data for remote execution

        Raises:
            ValidationError: If arguments don't match request schema
        """
        # Validate arguments using request schema
        request_obj = cls.request_schema(**kwargs)

        # Return as dictionary for JSON serialization
        return request_obj.model_dump()

    @classmethod
    def from_remote_response(cls, response_data: Dict[str, Any]) -> Any:
        """
        Convert remote response data to local return format.

        Validates the response using the response schema and converts
        it to the appropriate local object (Survey, Agent, etc.).

        Args:
            response_data: Raw response data from remote server

        Returns:
            Any: Local object instance (validated response)

        Raises:
            ValidationError: If response doesn't match response schema
        """
        # Validate response using response schema
        response_obj = cls.response_schema(**response_data)

        # For now, just return the validated response object
        # Subclasses can override to convert to specific object types
        return response_obj

    @classmethod
    def get_handler_info(cls) -> Dict[str, Any]:
        """
        Get handler registration information.

        Returns:
            dict: Handler metadata from registry
        """
        return RegisterVibesMethodsMeta.get_method_handler(
            cls.vibes_target, cls.vibes_method
        )

    @classmethod
    def validate_registration(cls) -> bool:
        """
        Validate that this handler is properly registered.

        Returns:
            bool: True if handler is registered correctly

        Raises:
            ValueError: If handler registration is invalid
        """
        if not hasattr(cls, "vibes_target") or not hasattr(cls, "vibes_method"):
            raise ValueError(
                f"{cls.__name__} must define vibes_target and vibes_method"
            )

        handler_info = cls.get_handler_info()
        if not handler_info:
            raise ValueError(
                f"{cls.__name__} is not registered for {cls.vibes_target}.{cls.vibes_method}"
            )

        # Validate that registered info matches class attributes
        expected_attrs = {
            "handler_class": cls.handler_class,
            "handler_function": cls.handler_function,
            "request_schema": cls.request_schema,
            "response_schema": cls.response_schema,
            "is_classmethod": cls.is_classmethod,
        }

        for attr_name, expected_value in expected_attrs.items():
            registered_value = handler_info.get(attr_name)
            if registered_value != expected_value:
                raise ValueError(
                    f"{cls.__name__} registration mismatch for {attr_name}: "
                    f"expected {expected_value}, registered {registered_value}"
                )

        return True

    @classmethod
    def get_request_example(cls) -> Dict[str, Any]:
        """
        Get an example request for this handler.

        Returns a sample request dictionary that would be valid
        for this handler's request schema.

        Returns:
            dict: Example request data

        Note:
            Subclasses should override this to provide meaningful examples.
        """
        # Try to get schema examples/defaults
        try:
            # Create empty instance to get default values
            example_request = cls.request_schema()
            return example_request.model_dump()
        except Exception:
            # Fallback to schema field info
            try:
                schema = cls.request_schema.model_json_schema()
                example = {}
                for field_name, field_info in schema.get("properties", {}).items():
                    if "example" in field_info:
                        example[field_name] = field_info["example"]
                    elif "default" in field_info:
                        example[field_name] = field_info["default"]
                    elif field_info.get("type") == "string":
                        example[field_name] = f"example_{field_name}"
                    elif field_info.get("type") == "integer":
                        example[field_name] = 1
                    elif field_info.get("type") == "number":
                        example[field_name] = 0.5
                    elif field_info.get("type") == "boolean":
                        example[field_name] = False

                return example
            except Exception:
                return {"example": "request"}

    @classmethod
    def get_response_example(cls) -> Dict[str, Any]:
        """
        Get an example response for this handler.

        Returns a sample response dictionary that would be valid
        for this handler's response schema.

        Returns:
            dict: Example response data

        Note:
            Subclasses should override this to provide meaningful examples.
        """
        # Similar logic to get_request_example but for response schema
        try:
            example_response = cls.response_schema()
            return example_response.model_dump()
        except Exception:
            try:
                schema = cls.response_schema.model_json_schema()
                example = {}
                for field_name, field_info in schema.get("properties", {}).items():
                    if "example" in field_info:
                        example[field_name] = field_info["example"]
                    elif "default" in field_info:
                        example[field_name] = field_info["default"]
                    elif field_info.get("type") == "string":
                        example[field_name] = f"example_{field_name}"
                    elif field_info.get("type") == "array":
                        example[field_name] = []
                    elif field_info.get("type") == "object":
                        example[field_name] = {}

                return example
            except Exception:
                return {"example": "response"}

    def __repr__(self):
        """String representation for debugging."""
        return (
            f"{self.__class__.__name__}("
            f"target={getattr(self, 'vibes_target', 'undefined')}, "
            f"method={getattr(self, 'vibes_method', 'undefined')}"
            f")"
        )


class VibesHandlerError(Exception):
    """
    Base exception for vibes handler errors.

    Raised when there are issues with handler registration,
    validation, or execution.
    """

    def __init__(
        self,
        message: str,
        handler_class: Optional[str] = None,
        target: Optional[str] = None,
        method: Optional[str] = None,
    ):
        super().__init__(message)
        self.handler_class = handler_class
        self.target = target
        self.method = method

    def __str__(self):
        parts = [super().__str__()]
        if self.handler_class:
            parts.append(f"Handler: {self.handler_class}")
        if self.target and self.method:
            parts.append(f"Target.Method: {self.target}.{self.method}")
        return " | ".join(parts)


# Utility functions for working with handlers


def get_all_registered_handlers() -> Dict[str, Dict[str, Any]]:
    """
    Get all registered vibes handlers.

    Returns:
        dict: Complete registry mapping targets to methods to handler info
    """
    return RegisterVibesMethodsMeta.get_registry()


def list_handlers_for_target(target: str) -> list[str]:
    """
    List all registered handlers for a specific target.

    Args:
        target: Target object type (e.g., "survey", "agent")

    Returns:
        list: List of method names available for the target
    """
    return RegisterVibesMethodsMeta.list_available_methods(target)


def is_handler_registered(target: str, method: str) -> bool:
    """
    Check if a handler is registered for a specific target and method.

    Args:
        target: Target object type (e.g., "survey", "agent")
        method: Method name (e.g., "from_vibes", "vibe_edit")

    Returns:
        bool: True if handler is registered
    """
    return RegisterVibesMethodsMeta.is_method_registered(target, method)


def validate_handler_request(target: str, method: str, **kwargs) -> Any:
    """
    Validate request parameters for a registered handler.

    Args:
        target: Target object type (e.g., "survey", "agent")
        method: Method name (e.g., "from_vibes", "vibe_edit")
        **kwargs: Request parameters to validate

    Returns:
        Validated request object

    Raises:
        ValueError: If handler not registered
        ValidationError: If parameters invalid
    """
    return RegisterVibesMethodsMeta.validate_request(target, method, **kwargs)


if __name__ == "__main__":
    # Example usage and testing
    print("Vibes Handler Base System")
    print("=" * 50)

    # Print current registry state
    print(RegisterVibesMethodsMeta.debug_registry())

    # Test utility functions
    print(f"\nRegistered handlers: {get_all_registered_handlers()}")

    for target in RegisterVibesMethodsMeta.list_available_targets():
        methods = list_handlers_for_target(target)
        print(f"Handlers for {target}: {methods}")

        for method in methods:
            print(
                f"  {target}.{method} registered: {is_handler_registered(target, method)}"
            )

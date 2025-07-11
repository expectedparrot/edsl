"""Extension Service classes for creating EDSL extension services.

This module provides the abstract base class and output classes for creating
extension services that can be easily integrated into the EDSL ecosystem.
"""

from abc import ABC, abstractmethod, ABCMeta
from typing import Dict, Any
from collections import UserDict
import re
import ast
import inspect


class ExtensionServiceMeta(ABCMeta):
    """Metaclass for ExtensionService that validates class attributes at definition time."""

    def __new__(mcs, name, bases, namespace, **kwargs):
        # Create the class first
        cls = super().__new__(mcs, name, bases, namespace, **kwargs)

        # Skip validation for the base ExtensionService class itself
        if name == "ExtensionService":
            return cls

            # Only validate if this is a concrete subclass of ExtensionService
        # Check by class name to avoid circular reference issues
        if any(getattr(base, "__name__", "") == "ExtensionService" for base in bases):
            mcs._validate_extension_service_class(cls)

        return cls

    @staticmethod
    def _validate_extension_service_class(cls):
        """Validate that the ExtensionService subclass has all required class attributes."""
        required_attrs = ["service_name", "description", "cost", "extension_outputs"]

        # Check for missing required attributes
        for attr in required_attrs:
            if not hasattr(cls, attr):
                raise AttributeError(
                    f"Class {cls.__name__} must define '{attr}' class attribute"
                )

        # Validate service_name format
        ExtensionServiceMeta._validate_service_name(cls)

        # Validate extension_outputs structure
        ExtensionServiceMeta._validate_extension_outputs(cls)

        # Validate that execute method exists and is properly defined
        ExtensionServiceMeta._validate_execute_method(cls)

    @staticmethod
    def _validate_service_name(cls):
        """Validate that service_name follows the required format."""
        service_name = getattr(cls, "service_name", None)

        if not isinstance(service_name, str):
            raise AttributeError(
                f"Class {cls.__name__} 'service_name' must be a string"
            )

        # Check if it's a valid Python identifier
        if not service_name.isidentifier():
            raise AttributeError(
                f"Class {cls.__name__} 'service_name' must be a valid Python identifier, got '{service_name}'"
            )

        # Check if it's all lowercase
        if service_name != service_name.lower():
            raise AttributeError(
                f"Class {cls.__name__} 'service_name' must be all lowercase, got '{service_name}'"
            )

        # Check for only letters, numbers, and underscores (no whitespace or special chars)
        if not re.match(r"^[a-z0-9_]+$", service_name):
            raise AttributeError(
                f"Class {cls.__name__} 'service_name' can only contain lowercase letters, numbers, and underscores, got '{service_name}'"
            )

        # Check for no whitespace (extra safety check)
        if " " in service_name or "\t" in service_name or "\n" in service_name:
            raise AttributeError(
                f"Class {cls.__name__} 'service_name' cannot contain whitespace, got '{service_name}'"
            )

    @staticmethod
    def _validate_extension_outputs(cls):
        """Validate that extension_outputs has the correct structure."""
        extension_outputs = getattr(cls, "extension_outputs", None)

        if not isinstance(extension_outputs, dict):
            raise AttributeError(
                f"Class {cls.__name__} 'extension_outputs' must be a dictionary"
            )

        for key, output_def in extension_outputs.items():
            if not isinstance(output_def, dict):
                raise AttributeError(
                    f"Output '{key}' in {cls.__name__}.extension_outputs must be a dictionary"
                )

            required_keys = ["output_type", "description", "returns_coopr_url"]
            for req_key in required_keys:
                if req_key not in output_def:
                    raise AttributeError(
                        f"Output '{key}' in {cls.__name__}.extension_outputs missing required field '{req_key}'"
                    )

            # Ensure 'value' is not included (that comes from execute())
            if "value" in output_def:
                raise AttributeError(
                    f"Output '{key}' in {cls.__name__}.extension_outputs should not include 'value' - values come from execute() method"
                )

    @staticmethod
    def _validate_execute_method(cls):
        """Validate that the execute method exists and is properly defined."""
        if not hasattr(cls, "execute"):
            raise AttributeError(
                f"Class {cls.__name__} must define an 'execute' method"
            )

        execute_method = getattr(cls, "execute")

        # Check if it's callable
        if not callable(execute_method):
            raise AttributeError(
                f"Class {cls.__name__} 'execute' method must be callable"
            )

        # Validate return signature using static code inspection
        ExtensionServiceMeta._validate_return_signature_static(cls)

    @staticmethod
    def _validate_return_signature_static(cls):
        """Validate return signature using static code inspection of the execute method."""
        try:
            # Get the execute method
            execute_method = getattr(cls, "execute")

            # Get the source code
            source = inspect.getsource(execute_method)

            # Remove common leading whitespace to handle indentation
            import textwrap

            source = textwrap.dedent(source)

            # Parse the source code into an AST
            tree = ast.parse(source)

            # Find all return statements
            return_visitor = ReturnStatementVisitor(cls.extension_outputs.keys())
            return_visitor.visit(tree)

            # Check if we found any problematic returns
            if return_visitor.validation_errors:
                error_msg = f"Class {cls.__name__} execute() method has return signature issues:\n"
                for error in return_visitor.validation_errors:
                    error_msg += f"  - {error}\n"
                raise AttributeError(error_msg.rstrip())

        except (OSError, TypeError, SyntaxError, IndentationError) as e:
            # If we can't get source (e.g., in REPL, compiled code), skip validation
            import warnings

            warnings.warn(
                f"Could not validate return signature for {cls.__name__}: {e}"
            )


class ReturnStatementVisitor(ast.NodeVisitor):
    """AST visitor that validates return statements in execute methods."""

    def __init__(self, expected_keys):
        self.expected_keys = set(expected_keys)
        self.validation_errors = []

    def visit_Return(self, node):
        """Visit a return statement and validate its structure."""
        if node.value is None:
            # Return with no value (return;)
            return

        if isinstance(node.value, ast.Dict):
            # Return statement is a dictionary literal
            self._validate_dict_return(node.value)
        # For non-dict returns (variables, function calls, etc.), we can't validate statically
        # but that's okay - runtime validation will catch those

    def _validate_dict_return(self, dict_node):
        """Validate a dictionary return statement."""
        # Extract string keys from the dictionary literal
        returned_keys = set()

        for key_node in dict_node.keys:
            if isinstance(key_node, ast.Str):  # Python < 3.8
                returned_keys.add(key_node.s)
            elif isinstance(key_node, ast.Constant) and isinstance(
                key_node.value, str
            ):  # Python >= 3.8
                returned_keys.add(key_node.value)
            # For non-string keys or computed keys, we can't validate statically

        # Only validate if we could extract all keys as strings
        if len(returned_keys) == len(dict_node.keys):
            missing_keys = self.expected_keys - returned_keys
            if missing_keys:
                self.validation_errors.append(
                    f"Missing required keys in return statement: {missing_keys}"
                )

            extra_keys = returned_keys - self.expected_keys
            if extra_keys:
                self.validation_errors.append(
                    f"Extra keys in return statement not defined in extension_outputs: {extra_keys}"
                )


class ExtensionOutput(UserDict):
    """A dictionary-like class representing a single extension output with output_type, description, returns_coopr_url, and value."""

    def __init__(
        self, output_type: str, description: str, returns_coopr_url: bool, value: Any
    ):
        super().__init__()
        self.data["output_type"] = output_type
        self.data["description"] = description
        self.data["returns_coopr_url"] = returns_coopr_url
        self.data["value"] = value

    @property
    def output_type(self) -> str:
        return self.data["output_type"]

    @property
    def description(self) -> str:
        return self.data["description"]

    @property
    def returns_coopr_url(self) -> bool:
        return self.data["returns_coopr_url"]

    @property
    def value(self) -> Any:
        return self.data["value"]


class ExtensionOutputs(UserDict):
    """A dictionary-like class representing the overall extension outputs containing multiple ExtensionOutput objects."""

    def __init__(self, **entries):
        super().__init__()
        for key, value in entries.items():
            if isinstance(value, dict) and not isinstance(value, ExtensionOutput):
                # Convert dict to ExtensionOutput if it has the right structure
                if all(
                    k in value
                    for k in [
                        "output_type",
                        "description",
                        "returns_coopr_url",
                        "value",
                    ]
                ):
                    self.data[key] = ExtensionOutput(
                        output_type=value["output_type"],
                        description=value["description"],
                        returns_coopr_url=value["returns_coopr_url"],
                        value=value["value"],
                    )
                else:
                    self.data[key] = value
            else:
                self.data[key] = value

    def add_entry(
        self,
        key: str,
        output_type: str,
        description: str,
        returns_coopr_url: bool,
        value: Any,
    ) -> "ExtensionOutputs":
        """Add a new extension output entry.

        Returns:
            Self for method chaining (fluent interface).
        """
        self.data[key] = ExtensionOutput(
            output_type, description, returns_coopr_url, value
        )
        return self


class ExtensionService(ABC, metaclass=ExtensionServiceMeta):
    """Abstract base class for all extension services.

    Extension services provide a structured way to define reusable functionality
    that can be deployed as microservices. Each service defines:

    - Metadata via class attributes (service_name, description, cost, extension_outputs)
    - Logic via the static execute method
    - Test data via the example_inputs property

    Class attributes are validated at class definition time via the metaclass.

    Example:
        from edsl import Survey

        class QuestionCountService(ExtensionService):
            service_name = "question_count"
            description = "Counts questions in a survey"
            cost = 10

            extension_outputs = {
                'num_questions': {
                    'output_type': 'int',
                    'description': 'Number of questions',
                    'returns_coopr_url': False
                }
            }

            @staticmethod
            def execute(survey: Survey) -> Dict[str, Any]:
                return {'num_questions': len(survey.questions)}

            @property
            def example_inputs(self) -> Dict[str, Any]:
                return {'survey': Survey.example()}
    """

    def __init__(self):
        """Initialize the extension service using class attributes.

        Note: Class attribute validation happens at class definition time via metaclass.
        """
        # Use the class attributes directly (they're already validated by metaclass)
        self.service_name = self.__class__.service_name
        self.description = self.__class__.description
        self.cost = self.__class__.cost
        self.extension_outputs = self.__class__.extension_outputs

    @staticmethod
    @abstractmethod
    def execute(**kwargs) -> Dict[str, Any]:
        """Execute the main service functionality.

        Args:
            **kwargs: Service-specific input parameters

        Returns:
            Dictionary mapping output keys (defined in extension_outputs) to their runtime values
        """
        pass

    @property
    @abstractmethod
    def example_inputs(self) -> Dict[str, Any]:
        """Provide example inputs for testing the service.

        Returns:
            A dictionary of example input parameters
        """
        pass

    def validate_inputs(self, **kwargs) -> bool:
        """Validate input parameters. Override if custom validation needed.

        Args:
            **kwargs: Input parameters to validate

        Returns:
            True if inputs are valid, False otherwise
        """
        return True

    def _combine_outputs_with_values(
        self, values: Dict[str, Any]
    ) -> "ExtensionOutputs":
        """Combine extension_outputs metadata with runtime values.

        Args:
            values: Dictionary of runtime values from execute()

        Returns:
            ExtensionOutputs with complete metadata and values
        """
        # Validate that all required outputs are provided
        missing_keys = set(self.extension_outputs.keys()) - set(values.keys())
        if missing_keys:
            raise ValueError(
                f"execute() must return values for all outputs defined in extension_outputs. Missing: {missing_keys}"
            )

        # Warn about extra keys
        extra_keys = set(values.keys()) - set(self.extension_outputs.keys())
        if extra_keys:
            import warnings

            warnings.warn(
                f"execute() returned extra keys not defined in extension_outputs: {extra_keys}"
            )

        # Combine metadata with values
        outputs = ExtensionOutputs()
        for key, output_def in self.extension_outputs.items():
            if key in values:
                outputs.add_entry(
                    key=key,
                    output_type=output_def["output_type"],
                    description=output_def["description"],
                    returns_coopr_url=output_def["returns_coopr_url"],
                    value=values[key],
                )

        return outputs

    @classmethod
    def run_example(cls) -> "ExtensionOutputs":
        """Run the service with example inputs for testing.

        Returns:
            ExtensionOutputs from running with example inputs
        """
        instance = cls()
        example_inputs = instance.example_inputs
        values = cls.execute(**example_inputs)  # Call static method
        return instance._combine_outputs_with_values(values)

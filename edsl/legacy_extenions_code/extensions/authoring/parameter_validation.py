from typing import Dict, Any, Type
from dataclasses import MISSING, dataclass
from abc import ABC

from .exceptions import ServiceParameterValidationError
from ...base import RegisterSubclassesMeta


@dataclass
class Parameters:
    """A class to handle parameter validation and preparation for service calls."""

    parameters: Dict[str, Any]  # Dictionary of ParameterDefinition objects

    def validate_call_parameters(self, params: Dict[str, Any]) -> None:
        """Validates that all required parameters are present and of the correct type for a call.

        Args:
            params: Dictionary of parameter values to validate

        Raises:
            ServiceParameterValidationError: If validation fails (missing required param or type mismatch).
        """
        for param_name, param_def in self.parameters.items():
            # Check for missing required parameters (only if no default is defined)
            if (
                param_def.required
                and param_name not in params
                and param_def.default_value is MISSING
            ):
                raise ServiceParameterValidationError(
                    f"Missing required parameter: {param_name}"
                )

            # Check type if parameter is provided
            if param_name in params:
                expected_type_str = param_def.type.lower()
                actual_value = params[param_name]
                type_mismatch = False

                # Basic type validation
                if expected_type_str in ("string", "str") and not isinstance(
                    actual_value, str
                ):
                    type_mismatch = True
                elif expected_type_str in ("int", "integer") and not isinstance(
                    actual_value, int
                ):
                    # Allow ints where floats are expected
                    if not (
                        expected_type_str in ("number", "float")
                        and isinstance(actual_value, int)
                    ):
                        type_mismatch = True
                elif expected_type_str in ("number", "float") and not isinstance(
                    actual_value, (int, float)
                ):
                    type_mismatch = True
                elif expected_type_str in ("bool", "boolean") and not isinstance(
                    actual_value, bool
                ):
                    type_mismatch = True
                elif expected_type_str in ("list", "array") and not isinstance(
                    actual_value, list
                ):
                    type_mismatch = True
                elif expected_type_str in ("dict", "object") and not isinstance(
                    actual_value, dict
                ):
                    type_mismatch = True
                # Add more complex type checks if needed (e.g., for custom EDSL objects)

                if type_mismatch:
                    raise ServiceParameterValidationError(
                        f"Parameter '{param_name}' has incorrect type. "
                        f"Expected '{param_def.type}', got '{type(actual_value).__name__}'"
                    )

    def prepare_parameters(self, **kwargs: Any) -> Dict[str, Any]:
        """Prepares the dictionary of parameters for the API call, serializing EDSL objects and including defaults.
        Assumes parameters have been validated by validate_call_parameters.

        Args:
            **kwargs: The parameters to prepare

        Returns:
            Dict[str, Any]: The prepared parameters
        """
        # Prepare payload, serializing EDSL objects and including defaults
        call_params = {}
        edsl_registry = RegisterSubclassesMeta.get_registry()

        for param_name, param_def in self.parameters.items():
            if param_name in kwargs:
                value = kwargs[param_name]
                expected_type_str = param_def.type

                # Check if the expected type is a registered EDSL type
                if expected_type_str in edsl_registry:
                    target_cls = edsl_registry[expected_type_str]
                    # Check if the provided value is an instance of this EDSL type
                    # and has a 'to_dict' method. Validation should have already ensured type match.
                    if isinstance(value, target_cls) and hasattr(value, "to_dict"):
                        call_params[param_name] = value.to_dict()  # Serialize
                    else:
                        # This case *shouldn't* happen if validate_call_parameters was called first
                        # and the registry/type definitions are consistent.
                        # Passing as-is might be risky. Assuming validation covers mismatches.
                        call_params[param_name] = value
                else:
                    # Not an EDSL type, pass as-is
                    call_params[param_name] = value
            elif param_def.default_value is not MISSING:
                # Use default value if provided parameter is missing
                call_params[param_name] = param_def.default_value

        return call_params

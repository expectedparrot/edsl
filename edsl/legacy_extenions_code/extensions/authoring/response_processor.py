from typing import Dict, Any
import json
import requests
from dataclasses import dataclass

from ...base import RegisterSubclassesMeta
from .exceptions import (
    ServiceDeserializationError,
    ServiceResponseError,
    ServiceOutputValidationError,
)


@dataclass
class ServiceResponseProcessor:
    """Handles deserialization and validation of service responses."""

    service_name: str
    service_returns: Dict[str, Any]  # Dictionary of ReturnDefinition objects

    def deserialize_single_value(
        self, return_key: str, return_def: Any, response_data: Dict[str, Any]
    ) -> Any:
        """Deserializes a single value from the response data based on its definition."""
        raw_value = response_data.get(return_key)
        if raw_value is None:
            raise ServiceDeserializationError(
                f"Expected return key '{return_key}' not found in response for service '{self.service_name}'."
            )

        return_type_str = return_def.type
        edsl_registry = RegisterSubclassesMeta.get_registry()

        # Check registered EDSL types
        if return_type_str in edsl_registry:
            target_cls = edsl_registry[return_type_str]
            try:
                # Ensure raw_value is a dict for from_dict
                if not isinstance(raw_value, dict):
                    raise ServiceDeserializationError(
                        f"Expected dict for EDSL type '{return_type_str}' key '{return_key}', got {type(raw_value).__name__}."
                    )
                return target_cls.from_dict(raw_value)
            except Exception as e:
                msg = f"Failed to deserialize response key '{return_key}' into {target_cls.__name__} for service '{self.service_name}'. Error: {e}"
                raise ServiceDeserializationError(msg) from e
        # Check standard Python types
        elif return_type_str in ("str", "string"):
            try:
                return str(raw_value)
            except ValueError as e:
                raise ServiceDeserializationError(
                    f"Could not convert value for key '{return_key}' to str."
                ) from e
        elif return_type_str in ("int", "integer"):
            try:
                return int(raw_value)
            except (ValueError, TypeError) as e:
                raise ServiceDeserializationError(
                    f"Could not convert value for key '{return_key}' to int."
                ) from e
        elif return_type_str in ("float", "number"):
            try:
                return float(raw_value)
            except (ValueError, TypeError) as e:
                raise ServiceDeserializationError(
                    f"Could not convert value for key '{return_key}' to float."
                ) from e
        elif return_type_str in ("bool", "boolean"):
            # Handle potential string representations of bool
            if isinstance(raw_value, str):
                if raw_value.lower() == "true":
                    return True
                elif raw_value.lower() == "false":
                    return False
            try:
                return bool(raw_value)
            except ValueError as e:
                raise ServiceDeserializationError(
                    f"Could not convert value for key '{return_key}' to bool."
                ) from e
        elif return_type_str in ("list", "array"):
            try:
                # Ensure it's actually list-like, basic check
                if not isinstance(raw_value, list):
                    raise TypeError  # Caught below
                return list(raw_value)
            except TypeError as e:
                raise ServiceDeserializationError(
                    f"Could not convert value for key '{return_key}' to list."
                ) from e
        elif return_type_str in ("dict", "object"):
            try:
                # Ensure it's actually dict-like, basic check
                if not isinstance(raw_value, dict):
                    raise TypeError  # Caught below
                return dict(raw_value)
            except (TypeError, ValueError) as e:
                raise ServiceDeserializationError(
                    f"Could not convert value for key '{return_key}' to dict."
                ) from e
        else:
            # Type not recognized - raise an error instead of returning raw value
            raise ServiceDeserializationError(
                f"Unrecognized return type '{return_type_str}' defined for key '{return_key}' in service '{self.service_name}'."
            )

    def deserialize_response(self, response: requests.Response) -> Any:
        """Deserializes the API response based on the service definition."""
        try:
            response_data = response.json()
        except json.JSONDecodeError as e:
            msg = f"Error decoding JSON response from service '{self.service_name}'. Response text: {response.text[:500]}..."
            raise ServiceResponseError(msg) from e

        # If no specific returns defined, return the raw data
        if not self.service_returns:
            return response_data

        deserialized_results = {}
        try:
            for return_key, return_def in self.service_returns.items():
                deserialized_value = self.deserialize_single_value(
                    return_key, return_def, response_data
                )
                deserialized_results[return_key] = deserialized_value
        except ServiceDeserializationError as e:
            raise e
        except Exception as e:
            raise ServiceDeserializationError(
                f"Unexpected error during response deserialization for service '{self.service_name}': {e}"
            ) from e

        return deserialized_results

    def validate_service_output(self, output_data: Dict[str, Any]) -> None:
        """
        Validates the structure and types of the service output dictionary against the 'service_returns' definition.

        Args:
            output_data: The dictionary returned by the service implementation.

        Raises:
            TypeError: If the output_data is not a dictionary.
            ServiceOutputValidationError: If a required return key is missing or a value has the wrong type.
        """
        if not isinstance(output_data, dict):
            raise TypeError(
                f"Service output must be a dictionary, but got {type(output_data).__name__}."
            )

        edsl_registry = RegisterSubclassesMeta.get_registry()
        TYPE_MAP = {
            "str": str,
            "string": str,
            "int": int,
            "integer": int,
            "float": float,
            "number": float,
            "bool": bool,
            "boolean": bool,
            "list": list,
            "array": list,
            "dict": dict,
            "object": dict,
        }

        for return_key, return_def in self.service_returns.items():
            # Check if the key exists in the output
            if return_key not in output_data:
                raise ServiceOutputValidationError(
                    f"Missing expected return key in service output: '{return_key}'"
                )

            actual_value = output_data[return_key]
            expected_type_str = return_def.type

            # Check if this is a metadata structure with a 'value' field
            if isinstance(actual_value, dict) and "value" in actual_value:
                # Extract the actual value for validation
                actual_value_to_validate = actual_value["value"]
            else:
                # Use the value directly
                actual_value_to_validate = actual_value

            # Type Validation
            expected_python_type = TYPE_MAP.get(expected_type_str.lower())

            if expected_type_str in edsl_registry:
                # For EDSL objects defined in returns, we expect a dictionary representation
                if not isinstance(actual_value_to_validate, dict):
                    raise ServiceOutputValidationError(
                        f"Type mismatch for return key '{return_key}'. "
                        f"Expected a dictionary representation of EDSL type '{expected_type_str}', "
                        f"but got type '{type(actual_value_to_validate).__name__}'."
                    )

            elif expected_python_type:
                # Basic Python types
                # Special case: allow int for float/number
                if expected_python_type in (float,) and isinstance(
                    actual_value_to_validate, int
                ):
                    pass  # Allow int where float/number is expected
                elif not isinstance(actual_value_to_validate, expected_python_type):
                    raise ServiceOutputValidationError(
                        f"Type mismatch for return key '{return_key}'. "
                        f"Expected type '{expected_type_str}' (mapped to {expected_python_type.__name__}), "
                        f"but got type '{type(actual_value_to_validate).__name__}'."
                    )
            else:
                raise ServiceOutputValidationError(
                    f"Unknown type '{expected_type_str}' defined for return key '{return_key}'. Cannot validate."
                )

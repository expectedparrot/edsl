from typing import Dict, Any, Type, List, Optional
from pydantic import create_model, Field, BaseModel

from ...base import RegisterSubclassesMeta

class ModelGenerator:
    """Handles generation of Pydantic models for FastAPI endpoints."""

    def __init__(self, service_name: str, parameters: Dict[str, Any], service_returns: Dict[str, Any]):
        self.service_name = service_name
        self.parameters = parameters
        self.service_returns = service_returns

    def get_request_model(self) -> Type[BaseModel]:
        """Dynamically creates a Pydantic model for the service parameters."""
        fields_definitions = {}
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
            "list": List[Any],
            "array": List[Any],
            "dict": Dict[str, Any],
            "object": Dict[str, Any],
        }

        for param_name, param_def in self.parameters.items():
            type_str = param_def.type
            python_type = TYPE_MAP.get(type_str.lower())

            # If not a basic type, check if it's a known EDSL type (expect dict)
            if python_type is None and type_str in edsl_registry:
                python_type = Dict[str, Any] # Expect serialized dict for EDSL objects
            elif python_type is None:
                python_type = Any # Default to Any if type is unknown

            default_value = param_def.default_value
            description = param_def.description

            if default_value is not None:
                # Parameter has a default value
                field_definition = Field(default=default_value, description=description)
                type_annotation = python_type
            else:
                # Parameter does not have a default value
                if param_def.required:
                    # Required parameter
                    field_definition = Field(description=description)
                    type_annotation = python_type
                else:
                    # Optional parameter (required=False, no default)
                    field_definition = Field(default=None, description=description)
                    type_annotation = Optional[python_type]

            fields_definitions[param_name] = (type_annotation, field_definition)

        # Create a suitable model name
        model_name = f"{self.service_name.replace('_', ' ').title().replace(' ', '')}Parameters"
        # Dynamically create the Pydantic model
        pydantic_model = create_model(
            model_name,
            **fields_definitions,
            __base__=BaseModel
        )
        return pydantic_model

    def get_response_model(self) -> Type[BaseModel]:
        """Dynamically creates a Pydantic model for the service return values."""
        fields_definitions = {}
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
            "list": List[Any],
            "array": List[Any],
            "dict": Dict[str, Any],
            "object": Dict[str, Any],
        }

        for return_key, return_def in self.service_returns.items():
            type_str = return_def.type
            python_type = TYPE_MAP.get(type_str.lower())

            # Check EDSL types (expect dict representation in response)
            if python_type is None and type_str in edsl_registry:
                python_type = Dict[str, Any]
            elif python_type is None:
                python_type = Any # Default to Any if type is unknown

            description = return_def.description

            # All return fields are effectively required in the response model
            field_definition = Field(description=description)
            type_annotation = python_type

            fields_definitions[return_key] = (type_annotation, field_definition)

        # Create a suitable model name
        model_name = f"{self.service_name.replace('_', ' ').title().replace(' ', '')}Response"
        # Dynamically create the Pydantic model
        pydantic_model = create_model(
            model_name,
            **fields_definitions,
            __base__=BaseModel
        )
        return pydantic_model 
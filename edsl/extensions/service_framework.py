"""
EDSL Service Framework

A framework that allows EDSL users to create web services without knowing FastAPI.
Users only need to write their EDSL logic and define input/output schemas using decorators.
The framework handles all the web service boilerplate.
"""

import inspect
import json
import os
import uvicorn
from functools import wraps
from typing import Dict, Any, List, Union, Optional, Type, get_type_hints
from pathlib import Path

try:
    from fastapi import FastAPI, HTTPException, Request
    from fastapi.responses import JSONResponse
    from pydantic import BaseModel, Field, create_model, ValidationError

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

from ..base.exceptions import EDSLException


class ServiceFrameworkException(EDSLException):
    """Exception raised by the service framework"""

    pass


class EDSLServiceFramework:
    """
    Core framework class that manages service configuration and FastAPI app generation
    """

    def __init__(self):
        if not FASTAPI_AVAILABLE:
            raise ServiceFrameworkException(
                "FastAPI is required for the service framework. "
                "Install with: pip install 'edsl[services]' or pip install fastapi uvicorn"
            )

        self.app = None
        self.service_config = {}
        self.input_params = {}
        self.output_schema = {}
        self.service_function = None
        self.cost_credits = 1

    def create_request_model(self) -> Type[BaseModel]:
        """Auto-generate Pydantic request model from input_params"""
        fields = {}

        for param_name, config in self.input_params.items():
            param_type = config["type"]
            field_kwargs = {}

            # Handle default values
            if "default" in config:
                field_kwargs["default"] = config["default"]
            elif config.get("required", True):
                field_kwargs["default"] = ...  # Required field
            else:
                field_kwargs["default"] = None

            # Add field description
            if "description" in config:
                field_kwargs["description"] = config["description"]

            # Add validation constraints
            if "min_value" in config:
                field_kwargs["ge"] = config["min_value"]
            if "max_value" in config:
                field_kwargs["le"] = config["max_value"]
            if "min_length" in config:
                field_kwargs["min_length"] = config["min_length"]
            if "max_length" in config:
                field_kwargs["max_length"] = config["max_length"]

            # Handle choices (enum-like validation)
            if "choices" in config:
                from enum import Enum

                choice_enum = Enum(
                    f"{param_name}_choices",
                    {str(choice): choice for choice in config["choices"]},
                )
                param_type = choice_enum

            fields[param_name] = (param_type, Field(**field_kwargs))

        # Always add ep_api_token as optional (framework will handle validation)
        fields["ep_api_token"] = (
            Optional[str],
            Field(default=None, description="Expected Parrot API key"),
        )

        return create_model("ServiceRequest", **fields)

    def create_response_model(self) -> Type[BaseModel]:
        """Auto-generate Pydantic response model from output_schema"""
        fields = {}

        for key, type_info in self.output_schema.items():
            if isinstance(type_info, str):
                python_type = self._convert_type_string(type_info)
            else:
                python_type = type_info

            fields[key] = (python_type, Field())

        return create_model("ServiceResponse", **fields)

    def _convert_type_string(self, type_str: str) -> Type:
        """Convert string type names to Python types"""
        type_mapping = {
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
            "any": Any,
        }
        return type_mapping.get(type_str.lower(), Any)

    def create_fastapi_app(self) -> FastAPI:
        """Create and configure the FastAPI application"""
        app = FastAPI(
            title=self.service_config.get("name", "EDSL Service"),
            description=self.service_config.get(
                "description", "An EDSL-powered service"
            ),
            version=self.service_config.get("version", "1.0.0"),
            docs_url="/docs",
            redoc_url="/redoc",
            openapi_url="/openapi.json",
        )

        # Create models
        RequestModel = self.create_request_model()
        ResponseModel = self.create_response_model()

        # Create the main endpoint
        endpoint_name = self.service_config.get("endpoint_name", "run")

        @app.post(
            f"/{endpoint_name}",
            response_model=ResponseModel,
            summary=self.service_config.get("name", "Run Service"),
            description=self.service_config.get(
                "description", "Execute the EDSL service"
            ),
            tags=["service"],
        )
        async def service_endpoint(request: RequestModel):
            try:
                # Convert request to function parameters
                params = request.dict()

                # Validate API token if service requires user account
                if self.service_config.get("uses_user_account", True):
                    if not params.get("ep_api_token"):
                        raise HTTPException(
                            status_code=400,
                            detail="API token is required for this service",
                        )

                # Call user's function
                if inspect.iscoroutinefunction(self.service_function):
                    result = await self.service_function(**params)
                else:
                    result = self.service_function(**params)

                # Validate and return response
                return ResponseModel(**result)

            except ValidationError as e:
                raise HTTPException(status_code=422, detail=e.errors())
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        # Add health check endpoint
        @app.get("/health", tags=["system"])
        async def health_check():
            return {
                "status": "healthy",
                "service": self.service_config.get("name", "EDSL Service"),
            }

        # Add service info endpoint
        @app.get("/info", tags=["system"])
        async def service_info():
            return {
                "name": self.service_config.get("name"),
                "description": self.service_config.get("description"),
                "version": self.service_config.get("version"),
                "cost_credits": self.cost_credits,
                "uses_user_account": self.service_config.get("uses_user_account", True),
                "input_parameters": list(self.input_params.keys()),
                "output_schema": self.output_schema,
            }

        self.app = app
        return app


# Global framework instance for decorators
_current_framework = None


def edsl_service(
    name: str,
    description: str,
    version: str = "1.0.0",
    endpoint_name: Optional[str] = None,
    uses_user_account: bool = True,
    cost_credits: int = 1,
):
    """
    Main decorator to define an EDSL service

    Args:
        name: Human-readable name of the service
        description: Description of what the service does
        version: Service version (semver format)
        endpoint_name: Custom endpoint name (defaults to function name)
        uses_user_account: Whether service needs user's API key
        cost_credits: Cost in credits per service call
    """

    def decorator(func):
        global _current_framework

        # Create new framework instance
        framework = EDSLServiceFramework()
        framework.service_config = {
            "name": name,
            "description": description,
            "version": version,
            "endpoint_name": endpoint_name or func.__name__.replace("_", "-"),
            "uses_user_account": uses_user_account,
        }
        framework.service_function = func
        framework.cost_credits = cost_credits

        # Store framework in function for other decorators
        func._edsl_framework = framework
        _current_framework = framework

        return func

    return decorator


def input_param(
    name: str,
    param_type: Type,
    required: bool = True,
    default: Any = None,
    description: str = "",
    min_value: Optional[Union[int, float]] = None,
    max_value: Optional[Union[int, float]] = None,
    min_length: Optional[int] = None,
    max_length: Optional[int] = None,
    choices: Optional[List[Any]] = None,
):
    """
    Decorator to define input parameters for the service

    Args:
        name: Parameter name
        param_type: Python type (str, int, float, bool, list, dict)
        required: Whether parameter is required
        default: Default value if not required
        description: Parameter description for documentation
        min_value: Minimum value for numeric types
        max_value: Maximum value for numeric types
        min_length: Minimum length for string/list types
        max_length: Maximum length for string/list types
        choices: List of valid choices for the parameter
    """

    def decorator(func):
        if not hasattr(func, "_edsl_framework"):
            raise ServiceFrameworkException(
                "@input_param must be used after @edsl_service"
            )

        param_config = {
            "type": param_type,
            "required": required,
            "description": description,
        }

        if not required and default is not None:
            param_config["default"] = default
        elif not required:
            param_config["default"] = None

        if min_value is not None:
            param_config["min_value"] = min_value
        if max_value is not None:
            param_config["max_value"] = max_value
        if min_length is not None:
            param_config["min_length"] = min_length
        if max_length is not None:
            param_config["max_length"] = max_length
        if choices is not None:
            param_config["choices"] = choices

        func._edsl_framework.input_params[name] = param_config
        return func

    return decorator


def output_schema(schema: Dict[str, Union[str, Type]]):
    """
    Decorator to define the output schema for the service

    Args:
        schema: Dictionary mapping output field names to types
                Types can be strings ("str", "int", "float", "bool", "list", "dict")
                or actual Python types (str, int, float, bool, List, Dict)
    """

    def decorator(func):
        if not hasattr(func, "_edsl_framework"):
            raise ServiceFrameworkException(
                "@output_schema must be used after @edsl_service"
            )

        func._edsl_framework.output_schema = schema
        return func

    return decorator


def run_service(
    service_function,
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
    log_level: str = "info",
):
    """
    Run the EDSL service

    Args:
        service_function: Function decorated with @edsl_service
        host: Host to bind to
        port: Port to bind to
        reload: Enable auto-reload for development
        log_level: Logging level
    """
    if not hasattr(service_function, "_edsl_framework"):
        raise ServiceFrameworkException("Function must be decorated with @edsl_service")

    framework = service_function._edsl_framework
    app = framework.create_fastapi_app()

    print(f"Starting EDSL service: {framework.service_config['name']}")
    print(
        f"Service endpoint: http://{host}:{port}/{framework.service_config['endpoint_name']}"
    )
    print(f"API docs: http://{host}:{port}/docs")

    uvicorn.run(app, host=host, port=port, reload=reload, log_level=log_level)


def generate_service_files(
    service_function, output_dir: str = ".", include_requirements: bool = True
):
    """
    Generate deployment files for the service

    Args:
        service_function: Function decorated with @edsl_service
        output_dir: Directory to write files to
        include_requirements: Whether to generate requirements.txt
    """
    if not hasattr(service_function, "_edsl_framework"):
        raise ServiceFrameworkException("Function must be decorated with @edsl_service")

    framework = service_function._edsl_framework
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)

    # Generate requirements.txt
    if include_requirements:
        requirements = [
            "edsl[services]",
            "fastapi",
            "uvicorn[standard]",
            "python-multipart",
        ]

        requirements_file = output_path / "requirements.txt"
        requirements_file.write_text("\n".join(requirements))
        print(f"Generated: {requirements_file}")

    # Generate service info JSON
    service_info = {
        "name": framework.service_config["name"],
        "description": framework.service_config["description"],
        "version": framework.service_config["version"],
        "endpoint_name": framework.service_config["endpoint_name"],
        "cost_credits": framework.cost_credits,
        "uses_user_account": framework.service_config["uses_user_account"],
        "input_parameters": framework.input_params,
        "output_schema": framework.output_schema,
    }

    info_file = output_path / "service_info.json"
    info_file.write_text(json.dumps(service_info, indent=2))
    print(f"Generated: {info_file}")


# Convenience functions for common patterns
def create_simple_service(name: str, description: str):
    """
    Create a simple service template

    Returns a partially configured decorator that users can apply to their function
    """
    return edsl_service(name=name, description=description)


def validate_service(service_function):
    """
    Validate that a service is properly configured

    Args:
        service_function: Function decorated with @edsl_service

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if not hasattr(service_function, "_edsl_framework"):
        errors.append("Function must be decorated with @edsl_service")
        return errors

    framework = service_function._edsl_framework

    # Check required configuration
    if not framework.service_config.get("name"):
        errors.append("Service name is required")

    if not framework.service_config.get("description"):
        errors.append("Service description is required")

    # Check that function signature matches input parameters
    sig = inspect.signature(service_function)
    func_params = set(sig.parameters.keys())
    declared_params = set(framework.input_params.keys())
    declared_params.add("ep_api_token")  # Always added by framework

    missing_params = declared_params - func_params
    if missing_params:
        errors.append(f"Function is missing parameters: {missing_params}")

    extra_params = func_params - declared_params
    if extra_params:
        errors.append(f"Function has undeclared parameters: {extra_params}")

    # Check output schema
    if not framework.output_schema:
        errors.append("Output schema is required (@output_schema decorator)")

    return errors

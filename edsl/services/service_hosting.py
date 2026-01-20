"""
EDSL Service Hosting - FastAPI infrastructure for exposing services as REST APIs.

This module provides the ServiceAPI class which creates a FastAPI application
from registered service classes. It handles introspection, serialization,
and dynamic endpoint generation.

Usage:
    from edsl.services import ServiceAPI
    from my_extension.service import MyService

    api = ServiceAPI()
    api.register_service(MyService)
    app = api.create_app(title="My Service API")

    # Run with: uvicorn my_server:app --reload
"""

from typing import Type, Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import create_model
import inspect
from enum import Enum


class MethodType(Enum):
    """Enumeration for different method types."""
    INSTANCE = "instance"
    CLASSMETHOD = "classmethod"
    STATIC = "static"


def get_service_info(cls: Type) -> dict:
    """
    Returns information about the service via introspection.

    This function works with any class that follows the service pattern,
    even if it doesn't inherit from ExternalService.

    Args:
        cls: A class to inspect

    Returns:
        dict: A dictionary containing service_name, description, extends, and methods
    """
    import re
    from typing import get_type_hints

    def parse_docstring(docstring: str) -> dict:
        """Parse a docstring to extract description, args, and returns."""
        if not docstring:
            return {'description': '', 'args': {}, 'returns': None}

        lines = docstring.strip().split('\n')
        description_lines = []
        args = {}
        returns = None

        current_section = 'description'
        current_arg = None

        for line in lines:
            stripped = line.strip()

            if stripped.lower().startswith('args:'):
                current_section = 'args'
                continue
            elif stripped.lower().startswith('returns:'):
                current_section = 'returns'
                continue

            if current_section == 'description':
                if stripped:
                    description_lines.append(stripped)
            elif current_section == 'args':
                arg_match = re.match(r'^(\w+)(?:\s*\(([^)]+)\))?:\s*(.*)$', stripped)
                if arg_match:
                    current_arg = arg_match.group(1)
                    args[current_arg] = {'description': arg_match.group(3).strip()}
                elif current_arg and stripped:
                    args[current_arg]['description'] += ' ' + stripped
            elif current_section == 'returns':
                return_match = re.match(r'^(\w+):\s*(.*)$', stripped)
                if return_match:
                    returns = return_match.group(2).strip()
                elif stripped:
                    returns = stripped

        return {
            'description': ' '.join(description_lines),
            'args': args,
            'returns': returns
        }

    def get_type_name(annotation) -> str:
        """Get a string representation of a type annotation."""
        if annotation is inspect.Parameter.empty:
            return 'Any'
        if hasattr(annotation, '__name__'):
            return annotation.__name__
        return str(annotation).replace('typing.', '')

    service_name = getattr(cls, 'service_name', cls.__name__)
    description = cls.__doc__.strip() if cls.__doc__ else ''

    extends = []
    if hasattr(cls, 'extends'):
        extends = [get_type_name(t) for t in cls.extends]

    methods = []

    for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
        if name.startswith('_'):
            continue

        if not hasattr(method, 'method_type'):
            continue

        method_type_value = method.method_type.value
        docstring_info = parse_docstring(method.__doc__)

        try:
            hints = get_type_hints(method)
        except Exception:
            hints = {}

        return_type = get_type_name(hints.get('return', inspect.Parameter.empty))

        sig = inspect.signature(method)
        parameters = {}

        for param_name, param in sig.parameters.items():
            if param_name in ('self', 'cls'):
                continue
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                continue

            param_type = get_type_name(hints.get(param_name, param.annotation))
            param_desc = docstring_info['args'].get(param_name, {}).get('description', '')
            has_default = param.default is not inspect.Parameter.empty

            parameters[param_name] = {
                'type': param_type,
                'description': param_desc,
                'required': not has_default,
                'default': param.default if has_default else None
            }

        # Check if method is decorated with @event (returns an Event object)
        is_event = getattr(method, '_returns_event', False)

        method_info = {
            'method_name': name,
            'method_type': method_type_value,
            'description': docstring_info['description'],
            'returns': return_type,
            'parameters': parameters,
            'is_event': is_event
        }

        methods.append(method_info)

    return {
        'service_name': service_name,
        'description': description,
        'extends': extends,
        'methods': methods
    }


def to_serializable(obj: Any) -> Any:
    """Recursively convert an object to JSON-serializable types."""
    if obj is None:
        return None
    elif isinstance(obj, (str, int, float, bool)):
        return obj
    elif isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [to_serializable(item) for item in obj]
    elif hasattr(obj, "to_dict"):
        return obj.to_dict()
    elif hasattr(obj, "model_dump"):
        return obj.model_dump()
    elif hasattr(obj, "dict"):
        return obj.dict()
    elif hasattr(obj, "__dict__"):
        return {
            k: to_serializable(v)
            for k, v in obj.__dict__.items()
            if not k.startswith("_")
        }
    else:
        return str(obj)


def deserialize_instance(data: Any, type_hint: str) -> Any:
    """
    Deserialize a dict to an EDSL object based on the type hint.

    Args:
        data: The raw data (usually a dict) to deserialize
        type_hint: The type annotation string (e.g., "ScenarioList")

    Returns:
        Deserialized EDSL object or raw data if no deserializer matches
    """
    if data is None or not isinstance(data, dict):
        return data

    # Check for edsl_class_name in the data itself
    edsl_class_name = data.get("edsl_class_name")
    target_class = edsl_class_name or type_hint

    if target_class == "ScenarioList" or "ScenarioList" in str(target_class):
        from edsl.scenarios import ScenarioList
        if "scenarios" in data:
            return ScenarioList.from_dict(data)
        elif isinstance(data, list):
            return ScenarioList.from_list_of_dicts(data)

    elif target_class == "Scenario" or "Scenario" in str(target_class):
        from edsl.scenarios import Scenario
        return Scenario.from_dict(data)

    elif target_class == "AgentList" or "AgentList" in str(target_class):
        from edsl.agents import AgentList
        return AgentList.from_dict(data)

    elif target_class == "Agent" or "Agent" in str(target_class):
        from edsl.agents import Agent
        return Agent.from_dict(data)

    # Return raw data if no deserializer matches
    return data


class ServiceAPI:
    """
    Creates a FastAPI application from service classes.

    This class handles:
    - Service registration and introspection
    - Dynamic endpoint generation for each service method
    - Request/response serialization
    - Error handling with detailed tracebacks

    Usage:
        from my_extension.service import MyService

        api = ServiceAPI()
        api.register_service(MyService)
        app = api.create_app(title="My Service API")

        # Run with: uvicorn server:app --reload
    """

    def __init__(self):
        self.services: Dict[str, Type] = {}
        self.service_instances: Dict[str, Any] = {}
        self.service_info: Dict[str, dict] = {}

    def register_service(self, service_cls: Type, instance: Any = None):
        """
        Register a service class with the API.

        Args:
            service_cls: The service class to register
            instance: Optional pre-created instance (created on demand if not provided)
        """
        # Create instance to get info (ExternalService subclasses have get_info as instance method)
        if instance is None:
            instance = service_cls()

        # Use instance method if available (ExternalService pattern), else fall back to standalone
        if hasattr(instance, 'get_info'):
            info = instance.get_info()
        else:
            info = get_service_info(service_cls)

        service_name = info['service_name']

        self.services[service_name] = service_cls
        self.service_info[service_name] = info
        self.service_instances[service_name] = instance

    def _get_instance(self, service_name: str) -> Any:
        """Get or create a service instance."""
        if service_name not in self.service_instances:
            self.service_instances[service_name] = self.services[service_name]()
        return self.service_instances[service_name]

    def create_app(self, title: str = "Service API", version: str = "1.0.0") -> FastAPI:
        """
        Create a FastAPI application with endpoints for all registered services.

        Args:
            title: API title
            version: API version

        Returns:
            FastAPI application
        """
        app = FastAPI(
            title=title,
            version=version,
            description="Dynamic API for registered services"
        )

        # Root endpoint - list all services
        @app.get("/", tags=["Discovery"])
        async def list_services():
            """List all registered services and their endpoints."""
            services = []
            for name, info in self.service_info.items():
                services.append({
                    "service_name": name,
                    "description": info["description"],
                    "extends": info["extends"],
                    "methods": [m["method_name"] for m in info["methods"]]
                })
            return {"services": services}

        # Lightweight endpoint - just return service names (for client-side caching)
        @app.get("/services", tags=["Discovery"])
        async def list_service_names():
            """List just the names of all registered services (lightweight)."""
            return {"service_names": list(self.service_info.keys())}

        # Create endpoints for each service
        for service_name, info in self.service_info.items():
            self._create_service_endpoints(app, service_name, info)

        return app

    def _create_service_endpoints(self, app: FastAPI, service_name: str, info: dict):
        """Create endpoints for a single service."""

        # Service info endpoint
        @app.get(f"/{service_name}", tags=[service_name])
        async def get_service_info(sn=service_name):
            """Get information about this service."""
            return self.service_info[sn]

        # Create method endpoints
        for method_info in info["methods"]:
            self._create_method_endpoint(app, service_name, method_info)

    def _create_method_endpoint(self, app: FastAPI, service_name: str, method_info: dict):
        """Create an endpoint for a single method."""
        method_name = method_info["method_name"]
        parameters = method_info["parameters"]

        # Build Pydantic model for request body
        fields = {}
        for param_name, param_info in parameters.items():
            param_type = self._get_python_type(param_info["type"])
            if param_info["required"]:
                fields[param_name] = (param_type, ...)
            else:
                fields[param_name] = (Optional[param_type], param_info.get("default"))

        # Create dynamic request model
        if fields:
            RequestModel = create_model(
                f"{service_name}_{method_name}_Request",
                **fields
            )
        else:
            RequestModel = None

        # Create the endpoint
        endpoint_path = f"/{service_name}/{method_name}"

        # Use factory functions to create proper closures
        def make_endpoint_with_body(svc_name, meth_name, meth_info, model):
            async def endpoint(request_body: model):  # type: ignore
                return await self._execute_method(
                    svc_name,
                    meth_name,
                    meth_info,
                    request_body.model_dump()
                )
            return endpoint

        def make_endpoint_no_body(svc_name, meth_name, meth_info):
            async def endpoint():
                return await self._execute_method(
                    svc_name,
                    meth_name,
                    meth_info,
                    {}
                )
            return endpoint

        if RequestModel:
            endpoint_func = make_endpoint_with_body(
                service_name, method_name, method_info, RequestModel
            )
        else:
            endpoint_func = make_endpoint_no_body(
                service_name, method_name, method_info
            )

        app.post(
            endpoint_path,
            tags=[service_name],
            summary=method_info["description"][:100] if method_info["description"] else method_name,
            description=method_info["description"]
        )(endpoint_func)

    async def _execute_method(
        self,
        service_name: str,
        method_name: str,
        method_info: dict,
        params: dict
    ) -> Any:
        """Execute a service method and return the result."""
        import traceback
        try:
            service_cls = self.services[service_name]
            method = getattr(service_cls, method_name)
            method_type = method_info["method_type"]

            # For instance methods, deserialize the 'instance' parameter if present
            if method_type == "instance" and "instance" in params:
                # Get the type hint for the instance parameter
                instance_type = method_info.get("parameters", {}).get("instance", {}).get("type", "Any")
                params["instance"] = deserialize_instance(params["instance"], instance_type)

            # Check if this is an event method
            is_event_method = method_info.get("is_event", False)

            # Execute based on method type
            if method_type == "static":
                result = method(**params)
            elif method_type == "classmethod":
                # Even if decorated as classmethod style, it might need an instance
                # if it uses self (like in FirecrawlService)
                service_instance = self._get_instance(service_name)
                result = method(service_instance, **params)
            else:  # instance method
                service_instance = self._get_instance(service_name)
                result = method(service_instance, **params)

            # Handle Event results specially
            if is_event_method and hasattr(result, 'name') and hasattr(result, 'payload'):
                # Result is an Event object - serialize with event metadata
                return {
                    "success": True,
                    "service": service_name,
                    "method": method_name,
                    "is_event": True,
                    "event_name": result.name,
                    "event_payload": to_serializable(result.payload),
                    "event_class": type(result).__name__
                }

            # Serialize the result
            serialized = to_serializable(result)

            return {
                "success": True,
                "service": service_name,
                "method": method_name,
                "result": serialized
            }

        except Exception as e:
            # Print full traceback to server console for debugging
            print(f"\n{'='*60}")
            print(f"ERROR in {service_name}.{method_name}")
            print(f"{'='*60}")
            traceback.print_exc()
            print(f"{'='*60}\n")

            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "service": service_name,
                    "method": method_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc()
                }
            )

    def _get_python_type(self, type_str: str) -> Type:
        """Convert a type string to a Python type."""
        type_mapping = {
            "str": str,
            "int": int,
            "float": float,
            "bool": bool,
            "list": list,
            "dict": dict,
            "List": list,
            "Dict": dict,
            "Any": Any,
        }

        # Handle union types like "str | list[str]"
        if "|" in type_str:
            return Any

        # Handle generic types like "list[str]"
        if "[" in type_str:
            base = type_str.split("[")[0]
            return type_mapping.get(base, Any)

        return type_mapping.get(type_str, Any)


def create_app_from_services(*service_classes: Type, title: str = "Service API") -> FastAPI:
    """
    Convenience function to create a FastAPI app from service classes.

    Args:
        *service_classes: Service classes to register
        title: API title

    Returns:
        FastAPI application

    Usage:
        from my_extension.service import MyService, OtherService

        app = create_app_from_services(MyService, OtherService, title="My API")
    """
    api = ServiceAPI()
    for cls in service_classes:
        api.register_service(cls)
    return api.create_app(title=title)

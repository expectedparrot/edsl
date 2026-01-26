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

import logging
import time
from typing import Type, Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import create_model
import inspect
from enum import Enum

logger = logging.getLogger("edsl.services")


# Task manager instance (initialized lazily)
_task_manager = None


def get_task_manager():
    """Get or create the task manager for background task support."""
    global _task_manager
    if _task_manager is None:
        try:
            from edsl.services_runner.config import get_config

            config = get_config()
            _task_manager = config.get_task_manager()
            if _task_manager is not None:
                logger.info(f"Task manager initialized: {type(_task_manager).__name__}")
            else:
                logger.warning(
                    "Task manager not configured (config.get_task_manager() returned None)"
                )
        except Exception as e:
            # Task queue not configured - background mode unavailable
            logger.warning(f"Task manager not available: {type(e).__name__}: {e}")
    return _task_manager


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
                arg_match = re.match(r"^(\w+)(?:\s*\(([^)]+)\))?:\s*(.*)$", stripped)
                if arg_match:
                    current_arg = arg_match.group(1)
                    args[current_arg] = {"description": arg_match.group(3).strip()}
                elif current_arg and stripped:
                    args[current_arg]["description"] += " " + stripped
            elif current_section == "returns":
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

    def get_type_name(annotation) -> str:
        """Get a string representation of a type annotation."""
        if annotation is inspect.Parameter.empty:
            return "Any"
        if hasattr(annotation, "__name__"):
            return annotation.__name__
        return str(annotation).replace("typing.", "")

    service_name = getattr(cls, "service_name", cls.__name__)
    description = cls.__doc__.strip() if cls.__doc__ else ""

    extends = []
    if hasattr(cls, "extends"):
        extends = [get_type_name(t) for t in cls.extends]

    methods = []

    for name, method in inspect.getmembers(cls, predicate=inspect.isfunction):
        if name.startswith("_"):
            continue

        if not hasattr(method, "method_type"):
            continue

        method_type_value = method.method_type.value
        docstring_info = parse_docstring(method.__doc__)

        try:
            hints = get_type_hints(method)
        except Exception:
            hints = {}

        return_type = get_type_name(hints.get("return", inspect.Parameter.empty))

        sig = inspect.signature(method)
        parameters = {}

        for param_name, param in sig.parameters.items():
            if param_name in ("self", "cls"):
                continue
            if param.kind == inspect.Parameter.VAR_KEYWORD:
                continue

            param_type = get_type_name(hints.get(param_name, param.annotation))
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

        # Check if method is decorated with @event (returns an Event object)
        is_event = getattr(method, "_returns_event", False)

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
    elif hasattr(obj, "to_transport_dict"):
        # FileStore uses to_transport_dict() to include file contents
        return obj.to_transport_dict()
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

    Supports multiple services with the same name as long as they extend
    different types. The correct service is selected based on the instance
    type at request time.

    Usage:
        from my_extension.service import MyService

        api = ServiceAPI()
        api.register_service(MyService)
        app = api.create_app(title="My Service API")

        # Run with: uvicorn server:app --reload
    """

    def __init__(self):
        # Nested structure: service_name -> {extends_type -> service_cls}
        self.services: Dict[str, Dict[str, Type]] = {}
        self.service_instances: Dict[str, Dict[str, Any]] = {}
        # Combined info for all services with the same name (methods merged)
        # Used for backwards-compatible discovery endpoint
        self.service_info: Dict[str, dict] = {}
        # Per-extends_type info: service_name -> {extends_type -> info_dict}
        # Used for routing to correct service
        self.service_info_by_type: Dict[str, Dict[str, dict]] = {}

    def register_service(self, service_cls: Type, instance: Any = None):
        """
        Register a service class with the API.

        Multiple services can have the same name if they extend different types.
        Methods are merged in service_info for endpoint generation.

        Args:
            service_cls: The service class to register
            instance: Optional pre-created instance (created on demand if not provided)
        """
        # Create instance to get info
        if instance is None:
            instance = service_cls()

        # Use instance method if available, else fall back to standalone
        if hasattr(instance, "get_info"):
            info = instance.get_info()
        else:
            info = get_service_info(service_cls)

        service_name = info["service_name"]
        extends_types = info.get("extends", [])

        logger.info(
            f"Registering service '{service_name}' from {service_cls.__name__} "
            f"(extends: {extends_types}, methods: {[m['method_name'] for m in info.get('methods', [])]})"
        )

        # Initialize nested dicts if needed
        if service_name not in self.services:
            self.services[service_name] = {}
            self.service_instances[service_name] = {}
            self.service_info_by_type[service_name] = {}

        # Register for each type it extends
        for extends_type in extends_types:
            if extends_type in self.services[service_name]:
                # Already registered for this type (same class is ok)
                existing = self.services[service_name][extends_type]
                if existing is not service_cls:
                    logger.warning(
                        f"Service '{service_name}' for type '{extends_type}' already "
                        f"registered by {existing.__name__}, skipping {service_cls.__name__}"
                    )
                continue

            self.services[service_name][extends_type] = service_cls
            self.service_instances[service_name][extends_type] = instance
            # Store per-type info for routing
            self.service_info_by_type[service_name][extends_type] = info
            logger.info(
                f"REGISTERED: services['{service_name}']['{extends_type}'] = {service_cls.__name__}"
            )

        # Log current state of service registry for this name
        logger.debug(
            f"Service registry for '{service_name}': {list(self.services[service_name].keys())}"
        )

        # Merge or create service_info (for backwards-compatible discovery)
        if service_name not in self.service_info:
            self.service_info[service_name] = info
        else:
            # Merge extends lists
            existing_extends = set(self.service_info[service_name].get("extends", []))
            existing_extends.update(extends_types)
            self.service_info[service_name]["extends"] = list(existing_extends)

            # Merge methods (avoid duplicates by method name)
            existing_methods = {
                m["method_name"]: m
                for m in self.service_info[service_name].get("methods", [])
            }
            for method in info.get("methods", []):
                if method["method_name"] not in existing_methods:
                    existing_methods[method["method_name"]] = method
            self.service_info[service_name]["methods"] = list(existing_methods.values())

    def _get_instance(
        self, service_name: str, extends_type: Optional[str] = None
    ) -> Any:
        """
        Get or create a service instance.

        Args:
            service_name: The service name
            extends_type: If specified, get instance for this specific type.
                         If None, returns the first available instance.
        """
        if service_name not in self.service_instances:
            return None

        type_map = self.service_instances[service_name]

        if extends_type is not None and extends_type in type_map:
            return type_map[extends_type]

        # Return first available
        if type_map:
            return next(iter(type_map.values()))
        return None

    def _get_service_cls(
        self, service_name: str, extends_type: Optional[str] = None
    ) -> Optional[Type]:
        """
        Get a service class by name and optionally by extends type.

        Args:
            service_name: The service name
            extends_type: If specified, get service for this specific type

        Returns:
            The service class, or None if not found

        Raises:
            ValueError: If extends_type is provided but not found in registered services
        """
        if service_name not in self.services:
            logger.warning(f"Service '{service_name}' not found in registered services")
            return None

        type_map = self.services[service_name]
        available_types = list(type_map.keys())

        # Enhanced logging for debugging service resolution
        lookup_msg = (
            f"SERVICE LOOKUP: '{service_name}' with extends_type={extends_type!r}, "
            f"available types: {available_types}"
        )
        logger.info(lookup_msg)

        if extends_type is not None:
            if extends_type in type_map:
                service_cls = type_map[extends_type]
                match_msg = f"SERVICE LOOKUP: Found exact match {service_cls.__name__} for type '{extends_type}'"
                logger.info(match_msg)
                return service_cls
            else:
                # extends_type was explicitly provided but not found - this is an error
                # Don't silently fall back to first available as this leads to
                # hard-to-debug bugs when multiple services share the same name
                error_msg = (
                    f"Service '{service_name}' does not extend type '{extends_type}'. "
                    f"Available types: {available_types}"
                )
                logger.error(f"SERVICE LOOKUP: {error_msg}")
                raise ValueError(error_msg)

        # No extends_type specified - return first available (for backwards compatibility)
        if type_map:
            if len(type_map) > 1:
                logger.warning(
                    f"SERVICE LOOKUP: Service '{service_name}' has multiple type variants "
                    f"{available_types} but no extends_type specified - using first available. "
                    f"This may cause incorrect behavior."
                )
            first_cls = next(iter(type_map.values()))
            logger.info(
                f"SERVICE LOOKUP: Returning first available: {first_cls.__name__}"
            )
            return first_cls
        return None

    def _resolve_service_for_instance(
        self, service_name: str, instance_data: Optional[dict]
    ) -> Optional[str]:
        """
        Determine which extends_type to use based on instance data.

        Args:
            service_name: The service name
            instance_data: The serialized instance dict (may have edsl_class_name)

        Returns:
            The extends_type to use, or None if can't determine
        """
        if instance_data is None:
            return None

        if service_name not in self.services:
            return None

        # Check for edsl_class_name in instance
        instance_type = instance_data.get("edsl_class_name")
        if instance_type and instance_type in self.services[service_name]:
            return instance_type

        # If only one service registered for this name, use it
        type_map = self.services[service_name]
        if len(type_map) == 1:
            return next(iter(type_map.keys()))

        return None

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
            description="Dynamic API for registered services",
        )

        # Root endpoint - list all services
        @app.get("/", tags=["Discovery"])
        async def list_services():
            """List all registered services and their endpoints."""
            services = []
            for name, info in self.service_info.items():
                services.append(
                    {
                        "service_name": name,
                        "description": info["description"],
                        "extends": info["extends"],
                        "methods": [m["method_name"] for m in info["methods"]],
                    }
                )
            return {"services": services}

        # Lightweight endpoint - just return service names (for client-side caching)
        @app.get("/services", tags=["Discovery"])
        async def list_service_names():
            """List just the names of all registered services (lightweight)."""
            return {"service_names": list(self.service_info.keys())}

        # Create endpoints for each service
        for service_name, info in self.service_info.items():
            self._create_service_endpoints(app, service_name, info)

        # Create task management endpoints
        self._create_task_endpoints(app)

        return app

    def _create_task_endpoints(self, app: FastAPI):
        """Create endpoints for task status and result retrieval."""

        @app.get("/tasks/{task_id}", tags=["Tasks"])
        async def get_task_status(task_id: str):
            """Get the status of a background task."""
            task_manager = get_task_manager()

            if task_manager is None:
                raise HTTPException(
                    status_code=503,
                    detail={"error": "Task queue not configured"},
                )

            status = task_manager.get_task_status(task_id)

            if status is None:
                raise HTTPException(
                    status_code=404,
                    detail={"error": f"Task {task_id} not found"},
                )

            return status.to_dict()

        @app.get("/tasks/{task_id}/result", tags=["Tasks"])
        async def get_task_result(task_id: str):
            """Get the result of a completed background task."""
            task_manager = get_task_manager()

            if task_manager is None:
                raise HTTPException(
                    status_code=503,
                    detail={"error": "Task queue not configured"},
                )

            # First check status
            status = task_manager.get_task_status(task_id)
            if status is None:
                raise HTTPException(
                    status_code=404,
                    detail={"error": f"Task {task_id} not found"},
                )

            if status.status.value == "failed":
                raise HTTPException(
                    status_code=500,
                    detail={
                        "error": status.error,
                        "error_type": status.error_type,
                    },
                )

            if status.status.value != "completed":
                raise HTTPException(
                    status_code=202,
                    detail={
                        "status": status.status.value,
                        "message": "Task not yet completed",
                    },
                )

            result = task_manager.get_task_result(task_id)
            if result is None:
                raise HTTPException(
                    status_code=404,
                    detail={"error": f"Result for task {task_id} not found"},
                )

            return result

        @app.post("/tasks/{task_id}/cancel", tags=["Tasks"])
        async def cancel_task(task_id: str):
            """Cancel a pending or running task."""
            task_manager = get_task_manager()

            if task_manager is None:
                raise HTTPException(
                    status_code=503,
                    detail={"error": "Task queue not configured"},
                )

            success = task_manager.cancel_task(task_id)

            if not success:
                raise HTTPException(
                    status_code=400,
                    detail={"error": f"Could not cancel task {task_id}"},
                )

            return {"success": True, "task_id": task_id, "status": "cancelled"}

    def _create_service_endpoints(self, app: FastAPI, service_name: str, info: dict):
        """Create endpoints for a single service."""

        # Service info endpoint (backwards compatible)
        @app.get(f"/{service_name}", tags=[service_name])
        async def get_service_info(sn=service_name):
            """Get information about this service (all extends types merged)."""
            return self.service_info[sn]

        # Create per-extends_type endpoints
        # This allows proper routing when multiple services share the same name
        for extends_type, type_info in self.service_info_by_type.get(
            service_name, {}
        ).items():
            # Service info endpoint per type
            @app.get(
                f"/{extends_type}/{service_name}",
                tags=[f"{extends_type}.{service_name}"],
            )
            async def get_typed_service_info(et=extends_type, sn=service_name):
                """Get information about this service for a specific type."""
                return self.service_info_by_type[sn][et]

            # Create method endpoints with type prefix
            for method_info in type_info["methods"]:
                self._create_method_endpoint(
                    app, service_name, method_info, extends_type=extends_type
                )

    def _create_method_endpoint(
        self,
        app: FastAPI,
        service_name: str,
        method_info: dict,
        extends_type: Optional[str] = None,
    ):
        """Create an endpoint for a single method.

        Args:
            app: FastAPI app
            service_name: Name of the service
            method_info: Method metadata
            extends_type: If provided, creates endpoint at /{extends_type}/{service_name}/{method}
                         Otherwise creates at /{service_name}/{method} (backwards compatible)
        """
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

        # Add background task support fields
        fields["background"] = (Optional[bool], False)
        fields["api_key"] = (Optional[str], None)
        # Add extends_type hint for service resolution when multiple services share name
        # Note: Cannot use underscore prefix (_extends_type) - Pydantic treats those as
        # private attributes and excludes them from model_dump()
        fields["extends_type"] = (Optional[str], None)

        # Create dynamic request model
        if fields:
            RequestModel = create_model(
                f"{service_name}_{method_name}_Request", **fields
            )
        else:
            RequestModel = None

        # Create the endpoint path
        if extends_type:
            endpoint_path = f"/{extends_type}/{service_name}/{method_name}"
            tag = f"{extends_type}.{service_name}"
        else:
            endpoint_path = f"/{service_name}/{method_name}"
            tag = service_name

        # Use factory functions to create proper closures
        def make_endpoint_with_body(
            svc_name, meth_name, meth_info, model, ext_type=None
        ):
            async def endpoint(request_body: model):  # type: ignore
                params = request_body.model_dump()
                # If extends_type is in the URL, use it (overrides body param)
                if ext_type:
                    params["extends_type"] = ext_type
                # Log at INFO level to always show this
                endpoint_msg = (
                    f"ENDPOINT /{ext_type or ''}/{svc_name}/{meth_name}: extends_type={params.get('extends_type')!r}, "
                    f"all keys={list(params.keys())}"
                )
                logger.info(endpoint_msg)
                print(endpoint_msg)  # Also print for visibility
                background = params.pop("background", False)
                api_key = params.pop("api_key", None)

                # Check if task queue is available
                task_manager = get_task_manager()
                if task_manager is not None:
                    # Always route through worker
                    return await self._submit_task_and_maybe_wait(
                        svc_name, meth_name, meth_info, params, api_key, background
                    )
                else:
                    # Fallback to direct execution if no task queue configured
                    logger.debug(
                        f"No task queue - executing {svc_name}.{meth_name} directly"
                    )
                    return await self._execute_method(
                        svc_name, meth_name, meth_info, params
                    )

            return endpoint

        def make_endpoint_no_body(svc_name, meth_name, meth_info, ext_type=None):
            async def endpoint():
                params = {}
                # If extends_type is in the URL, use it
                if ext_type:
                    params["extends_type"] = ext_type
                # Check if task queue is available
                task_manager = get_task_manager()
                if task_manager is not None:
                    return await self._submit_task_and_maybe_wait(
                        svc_name, meth_name, meth_info, params, None, background=False
                    )
                else:
                    logger.debug(
                        f"No task queue - executing {svc_name}.{meth_name} directly"
                    )
                    return await self._execute_method(
                        svc_name, meth_name, meth_info, params
                    )

            return endpoint

        if RequestModel:
            endpoint_func = make_endpoint_with_body(
                service_name, method_name, method_info, RequestModel, extends_type
            )
        else:
            endpoint_func = make_endpoint_no_body(
                service_name, method_name, method_info, extends_type
            )

        app.post(
            endpoint_path,
            tags=[tag],
            summary=(
                method_info["description"][:100]
                if method_info["description"]
                else method_name
            ),
            description=method_info["description"],
        )(endpoint_func)

    async def _execute_method(
        self, service_name: str, method_name: str, method_info: dict, params: dict
    ) -> Any:
        """Execute a service method and return the result."""
        import traceback

        start_time = time.time()
        logger.debug(f"Executing {service_name}.{method_name} (sync)")

        try:
            # Extract and remove the extends_type hint from params (not a real parameter)
            extends_type = params.pop("extends_type", None)
            exec_msg = (
                f"EXECUTE {service_name}.{method_name}: extends_type={extends_type!r} "
                f"(type={type(extends_type).__name__})"
            )
            logger.info(exec_msg)
            print(exec_msg)  # Also print for visibility

            # If no explicit extends_type, try to resolve from instance data
            if extends_type is None:
                instance_data = params.get("instance")
                if instance_data and isinstance(instance_data, dict):
                    extends_type = self._resolve_service_for_instance(
                        service_name, instance_data
                    )
                    logger.debug(
                        f"Resolved extends_type from instance data: {extends_type!r}"
                    )

            # Note: _get_service_cls raises ValueError if extends_type is provided but not found
            try:
                service_cls = self._get_service_cls(service_name, extends_type)
            except ValueError:
                # Re-raise - the error message from _get_service_cls is already descriptive
                raise

            if service_cls is None:
                raise ValueError(
                    f"No service found for '{service_name}' (extends_type={extends_type})"
                )

            method = getattr(service_cls, method_name)
            method_type = method_info["method_type"]

            # For instance methods, deserialize the 'instance' parameter if present
            if method_type == "instance" and "instance" in params:
                # Get the type hint for the instance parameter
                instance_type = (
                    method_info.get("parameters", {})
                    .get("instance", {})
                    .get("type", "Any")
                )
                params["instance"] = deserialize_instance(
                    params["instance"], instance_type
                )

            # Check if this is an event method
            is_event_method = method_info.get("is_event", False)

            # Execute based on method type
            if method_type == "static":
                result = method(**params)
            elif method_type == "classmethod":
                # Even if decorated as classmethod style, it might need an instance
                # if it uses self (like in FirecrawlService)
                service_instance = self._get_instance(service_name, extends_type)
                result = method(service_instance, **params)
            else:  # instance method
                service_instance = self._get_instance(service_name, extends_type)
                result = method(service_instance, **params)

            # Handle Event results specially
            if (
                is_event_method
                and hasattr(result, "name")
                and hasattr(result, "payload")
            ):
                # Result is an Event object - serialize with event metadata
                return {
                    "success": True,
                    "service": service_name,
                    "method": method_name,
                    "is_event": True,
                    "event_name": result.name,
                    "event_payload": to_serializable(result.payload),
                    "event_class": type(result).__name__,
                }

            # Serialize the result
            serialized = to_serializable(result)

            duration_ms = (time.time() - start_time) * 1000
            logger.debug(
                f"Completed {service_name}.{method_name} ({duration_ms:.1f}ms)"
            )

            return {
                "success": True,
                "service": service_name,
                "method": method_name,
                "result": serialized,
            }

        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Error in {service_name}.{method_name} ({duration_ms:.1f}ms): "
                f"{type(e).__name__}: {e}"
            )
            logger.debug(f"Traceback:\n{traceback.format_exc()}")

            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "service": service_name,
                    "method": method_name,
                    "error": str(e),
                    "error_type": type(e).__name__,
                    "traceback": traceback.format_exc(),
                },
            )

    async def _submit_task_and_maybe_wait(
        self,
        service_name: str,
        method_name: str,
        method_info: dict,
        params: dict,
        api_key: Optional[str] = None,
        background: bool = False,
    ) -> dict:
        """
        Submit a task to the worker queue.

        If background=True, returns immediately with task_id.
        If background=False, polls until complete and returns the result.
        """
        import asyncio

        task_manager = get_task_manager()

        if task_manager is None:
            logger.warning(
                f"Task queue not configured for {service_name}.{method_name}"
            )
            raise HTTPException(
                status_code=503,
                detail={
                    "success": False,
                    "error": "Task queue not configured",
                    "error_type": "ServiceUnavailable",
                },
            )

        try:
            logger.info(
                f"Submitting task: {service_name}.{method_name} "
                f"(background={background})"
            )
            task_id = task_manager.submit_task(
                service_name=service_name,
                method_name=method_name,
                params=params,
                api_key=api_key,
            )

            logger.info(
                f"Task submitted: {service_name}.{method_name} -> {task_id[:8]}"
            )

            # If background mode, return immediately
            if background:
                return {
                    "success": True,
                    "background": True,
                    "task_id": task_id,
                    "status_url": f"/tasks/{task_id}",
                    "result_url": f"/tasks/{task_id}/result",
                }

            # Synchronous mode: poll until complete
            logger.debug(f"[{task_id[:8]}] Waiting for task completion...")
            poll_interval = 0.1  # Start with 100ms
            max_poll_interval = 2.0  # Max 2 seconds between polls
            total_wait = 0
            timeout = 600  # 10 minute timeout

            while total_wait < timeout:
                status = task_manager.get_task_status(task_id)

                if status is None:
                    logger.error(f"[{task_id[:8]}] Task status not found")
                    raise HTTPException(
                        status_code=500,
                        detail={"error": f"Task {task_id} status not found"},
                    )

                if status.status.value == "completed":
                    logger.info(f"[{task_id[:8]}] Task completed, fetching result")
                    task_result = task_manager.get_task_result(task_id)
                    # Extract just the result data, not the full task metadata
                    result = task_result.get("result") if task_result else None
                    return {
                        "success": True,
                        "service": service_name,
                        "method": method_name,
                        "result": result,
                    }

                if status.status.value == "failed":
                    logger.error(
                        f"[{task_id[:8]}] Task failed: {status.error_type}: {status.error}"
                    )
                    raise HTTPException(
                        status_code=500,
                        detail={
                            "success": False,
                            "service": service_name,
                            "method": method_name,
                            "error": status.error,
                            "error_type": status.error_type,
                        },
                    )

                # Still running or queued - wait and poll again
                await asyncio.sleep(poll_interval)
                total_wait += poll_interval
                # Exponential backoff up to max
                poll_interval = min(poll_interval * 1.5, max_poll_interval)

            # Timeout reached
            logger.error(f"[{task_id[:8]}] Task timed out after {timeout}s")
            raise HTTPException(
                status_code=504,
                detail={
                    "success": False,
                    "error": f"Task {task_id} timed out after {timeout}s",
                    "error_type": "Timeout",
                    "task_id": task_id,
                },
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to submit task for {service_name}.{method_name}: {e}")
            raise HTTPException(
                status_code=500,
                detail={
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
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


def create_app_from_services(
    *service_classes: Type, title: str = "Service API"
) -> FastAPI:
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

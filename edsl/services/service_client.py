"""
EDSL Service Client - Dynamic client for service APIs.

Provides a clean attribute-access interface to call remote services
and deserialize results back to proper EDSL types.

The recommended approach is to use the ServiceEnabledMeta metaclass, which
automatically filters services based on their `extends` field:

Usage:
    from service_client import ScenarioList, ServiceEnabledMeta
    
    # Configure API endpoint (optional, defaults to localhost:8008)
    ServiceEnabledMeta.configure(base_url="http://localhost:8008")
    
    # Create a ScenarioList with data
    sl = ScenarioList([{"name": "test"}])
    
    # Access services that extend ScenarioList (e.g., firecrawl)
    results = sl.firecrawl.scrape(url="https://example.com")
    print(results)  # ScenarioList([Scenario({...})])
    
    # Services that don't extend ScenarioList raise AttributeError
    # sl.some_agent_service.foo()  # AttributeError!

For custom classes, use the metaclass directly:
    
    from service_client import ServiceEnabledMeta
    
    class MyCollection(metaclass=ServiceEnabledMeta):
        def __init__(self, data):
            self._data = data
        
        def to_dict(self):
            return {"data": self._data}
    
    # Now MyCollection instances can access services that extend "MyCollection"
"""

from typing import Any, Dict, List, Optional, Type
import requests


class ServiceClient:
    """
    Base HTTP client for communicating with the service API.

    Handles all HTTP requests and provides methods for discovering
    and calling remote services.
    """

    def __init__(self, base_url: str = "http://localhost:8008"):
        self.base_url = base_url.rstrip("/")
        self._services_cache: Optional[Dict[str, dict]] = None

    def get_services(self) -> List[dict]:
        """
        Fetch list of all available services from the API.

        Returns:
            List of service info dicts with service_name, description, methods
        """
        response = requests.get(f"{self.base_url}/")
        response.raise_for_status()
        return response.json().get("services", [])

    def get_service_info(self, service_name: str) -> dict:
        """
        Fetch detailed information about a specific service.

        Args:
            service_name: Name of the service to query

        Returns:
            Dict containing service_name, description, extends, and methods
        """
        response = requests.get(f"{self.base_url}/{service_name}")
        response.raise_for_status()
        return response.json()

    def call_method(self, service_name: str, method_name: str, params: dict) -> dict:
        """
        Call a method on a remote service.

        Args:
            service_name: Name of the service
            method_name: Name of the method to call
            params: Parameters to pass to the method

        Returns:
            Response dict with success, service, method, and result fields
        """
        url = f"{self.base_url}/{service_name}/{method_name}"
        response = requests.post(url, json=params)

        # Handle errors with more detail
        if response.status_code >= 400:
            try:
                detail = response.json().get("detail", {})
                if isinstance(detail, dict):
                    error_msg = detail.get("error", "Unknown error")
                    error_type = detail.get("error_type", "Exception")
                    tb = detail.get("traceback", "")

                    full_msg = f"{error_type}: {error_msg}"
                    if tb:
                        full_msg += f"\n\nServer traceback:\n{tb}"

                    raise RuntimeError(full_msg)
            except (ValueError, KeyError):
                pass
            response.raise_for_status()

        return response.json()


def serialize_param(value: Any) -> Any:
    """
    Serialize a parameter value for transmission to the API.

    Handles EDSL objects like Scenario, ScenarioList, Agent, etc.
    by calling their to_dict() method.

    Args:
        value: The parameter value to serialize

    Returns:
        JSON-serializable version of the value
    """
    if value is None:
        return None
    elif isinstance(value, (str, int, float, bool)):
        return value
    elif isinstance(value, dict):
        return {k: serialize_param(v) for k, v in value.items()}
    elif isinstance(value, (list, tuple)):
        return [serialize_param(item) for item in value]
    elif hasattr(value, "to_dict"):
        return value.to_dict()
    elif hasattr(value, "model_dump"):
        return value.model_dump()
    elif hasattr(value, "dict"):
        return value.dict()
    else:
        # Return as-is and let json encoder handle it or fail
        return value


def deserialize_result(result: Any, return_type: str) -> Any:
    """
    Deserialize an API result based on its return type.

    Checks for edsl_class_name in the result and uses the appropriate
    from_dict method to reconstruct the EDSL object.

    Args:
        result: The raw result from the API
        return_type: The declared return type from method info

    Returns:
        Deserialized EDSL object or raw result if no deserializer available
    """
    if result is None:
        return None

    if not isinstance(result, dict):
        return result

    # Check for EDSL class marker
    edsl_class_name = result.get("edsl_class_name")

    # Try to deserialize based on class name or return type
    target_class = edsl_class_name or return_type

    if target_class == "ScenarioList" or "ScenarioList" in str(target_class):
        from edsl.scenarios import ScenarioList

        # Check if it has the expected structure
        if "scenarios" in result:
            return ScenarioList.from_dict(result)
        # If it's a list of dicts (raw data), use from_list_of_dicts
        elif isinstance(result, list):
            return ScenarioList.from_list_of_dicts(result)

    elif target_class == "Scenario" or "Scenario" in str(target_class):
        from edsl.scenarios import Scenario

        return Scenario.from_dict(result)

    elif target_class == "AgentList" or "AgentList" in str(target_class):
        from edsl.agents import AgentList

        return AgentList.from_dict(result)

    elif target_class == "Agent" or "Agent" in str(target_class):
        from edsl.agents import Agent

        return Agent.from_dict(result)

    # Return raw result if no deserializer matches
    return result


class MethodProxy:
    """
    Proxy for a single service method.

    Wraps a remote method call, handling parameter passing and
    result deserialization.
    """

    def __init__(self, client: ServiceClient, service_name: str, method_info: dict):
        self.client = client
        self.service_name = service_name
        self.method_info = method_info
        self.method_name = method_info["method_name"]
        self.parameters = method_info.get("parameters", {})
        self.return_type = method_info.get("returns", "Any")
        self.description = method_info.get("description", "")

        # Set docstring for help()
        self.__doc__ = self._build_docstring()

    def _build_docstring(self) -> str:
        """Build a docstring from method info."""
        lines = [self.description, "", "Parameters:"]

        for name, info in self.parameters.items():
            param_type = info.get("type", "Any")
            param_desc = info.get("description", "")
            required = info.get("required", True)
            req_str = "" if required else " (optional)"
            lines.append(f"    {name} ({param_type}){req_str}: {param_desc}")

        lines.extend(["", f"Returns:", f"    {self.return_type}"])

        return "\n".join(lines)

    def __call__(self, *args, **kwargs) -> Any:
        """
        Call the remote method with the given parameters.

        Args:
            *args: Positional arguments (mapped to parameters in order)
            **kwargs: Keyword arguments

        Returns:
            Deserialized result from the API
        """
        # Map positional arguments to parameter names
        param_names = list(self.parameters.keys())
        for i, arg in enumerate(args):
            if i < len(param_names):
                param_name = param_names[i]
                if param_name in kwargs:
                    raise TypeError(
                        f"{self.method_name}() got multiple values for argument '{param_name}'"
                    )
                kwargs[param_name] = arg
            else:
                raise TypeError(
                    f"{self.method_name}() takes {len(param_names)} positional arguments "
                    f"but {len(args)} were given"
                )

        # Serialize all parameters for JSON transmission
        serialized_kwargs = {k: serialize_param(v) for k, v in kwargs.items()}

        # Call the API
        response = self.client.call_method(
            self.service_name, self.method_name, serialized_kwargs
        )

        # Check for success
        if not response.get("success", False):
            error = response.get("error", "Unknown error")
            error_type = response.get("error_type", "Exception")
            raise RuntimeError(f"{error_type}: {error}")

        # Deserialize and return the result
        result = response.get("result")
        return deserialize_result(result, self.return_type)

    def __repr__(self) -> str:
        params = ", ".join(
            f"{name}: {info.get('type', 'Any')}"
            for name, info in self.parameters.items()
        )
        return f"<MethodProxy {self.service_name}.{self.method_name}({params}) -> {self.return_type}>"


class ServiceProxy:
    """
    Proxy for a remote service.

    Provides attribute access to methods on the service.
    """

    def __init__(self, client: ServiceClient, service_name: str):
        self.client = client
        self.service_name = service_name
        self._service_info: Optional[dict] = None
        self._method_proxies: Dict[str, MethodProxy] = {}

    @property
    def service_info(self) -> dict:
        """Lazy-load service info from API."""
        if self._service_info is None:
            self._service_info = self.client.get_service_info(self.service_name)
        return self._service_info

    @property
    def methods(self) -> List[str]:
        """List available method names."""
        return [m["method_name"] for m in self.service_info.get("methods", [])]

    def __getattr__(self, name: str) -> MethodProxy:
        """Get a method proxy by name."""
        # Check cache first
        if name in self._method_proxies:
            return self._method_proxies[name]

        # Find method info
        for method_info in self.service_info.get("methods", []):
            if method_info["method_name"] == name:
                proxy = MethodProxy(self.client, self.service_name, method_info)
                self._method_proxies[name] = proxy
                return proxy

        raise AttributeError(
            f"Service '{self.service_name}' has no method '{name}'. "
            f"Available methods: {self.methods}"
        )

    def __repr__(self) -> str:
        return f"<ServiceProxy '{self.service_name}' methods={self.methods}>"

    def __dir__(self) -> List[str]:
        """Include available methods in dir() output."""
        return list(super().__dir__()) + self.methods


class InstanceMethodProxy:
    """
    Proxy for a service method bound to a specific EDSL object instance.

    Automatically serializes the bound instance and includes it as the
    'instance' parameter when calling the remote method.
    """

    def __init__(
        self,
        client: ServiceClient,
        service_name: str,
        method_info: dict,
        bound_instance: Any,
    ):
        self.client = client
        self.service_name = service_name
        self.method_info = method_info
        self.method_name = method_info["method_name"]
        self.method_type = method_info.get("method_type", "instance")
        self.parameters = method_info.get("parameters", {})
        self.return_type = method_info.get("returns", "Any")
        self.description = method_info.get("description", "")
        self.is_event = method_info.get("is_event", False)
        self.bound_instance = bound_instance

        # Set docstring for help()
        self.__doc__ = self._build_docstring()

    def _build_docstring(self) -> str:
        """Build a docstring from method info."""
        lines = [self.description, "", "Parameters:"]

        for name, info in self.parameters.items():
            # Skip 'instance' parameter in docstring since it's auto-populated
            if name == "instance":
                continue
            param_type = info.get("type", "Any")
            param_desc = info.get("description", "")
            required = info.get("required", True)
            req_str = "" if required else " (optional)"
            lines.append(f"    {name} ({param_type}){req_str}: {param_desc}")

        lines.extend(["", f"Returns:", f"    {self.return_type}"])

        return "\n".join(lines)

    def _serialize_instance(self) -> Any:
        """Serialize the bound instance to a dict for transmission."""
        if hasattr(self.bound_instance, "to_dict"):
            return self.bound_instance.to_dict()
        elif hasattr(self.bound_instance, "model_dump"):
            return self.bound_instance.model_dump()
        elif hasattr(self.bound_instance, "dict"):
            return self.bound_instance.dict()
        else:
            raise TypeError(
                f"Cannot serialize instance of type {type(self.bound_instance).__name__}. "
                "Instance must have a to_dict(), model_dump(), or dict() method."
            )

    def __call__(self, *args, **kwargs) -> Any:
        """
        Call the remote method with the given parameters.

        For instance methods, automatically includes the serialized bound
        instance as the 'instance' parameter.

        Args:
            *args: Positional arguments (mapped to non-instance parameters)
            **kwargs: Keyword arguments

        Returns:
            Deserialized result from the API
        """
        # For instance methods, include the serialized bound instance
        if self.method_type == "instance":
            kwargs["instance"] = self._serialize_instance()

        # Map positional arguments to parameter names (excluding 'instance')
        param_names = [name for name in self.parameters.keys() if name != "instance"]
        for i, arg in enumerate(args):
            if i < len(param_names):
                param_name = param_names[i]
                if param_name in kwargs:
                    raise TypeError(
                        f"{self.method_name}() got multiple values for argument '{param_name}'"
                    )
                kwargs[param_name] = arg
            else:
                raise TypeError(
                    f"{self.method_name}() takes {len(param_names)} positional arguments "
                    f"but {len(args)} were given"
                )

        # Serialize all parameters for JSON transmission
        serialized_kwargs = {k: serialize_param(v) for k, v in kwargs.items()}

        # Call the API
        response = self.client.call_method(
            self.service_name, self.method_name, serialized_kwargs
        )

        # Check for success
        if not response.get("success", False):
            error = response.get("error", "Unknown error")
            error_type = response.get("error_type", "Exception")
            raise RuntimeError(f"{error_type}: {error}")

        # Handle event responses - apply event to bound instance
        if response.get("is_event", False):
            return self._apply_event_response(response)

        # Deserialize and return the result
        result = response.get("result")
        return deserialize_result(result, self.return_type)

    def _apply_event_response(self, response: dict) -> Any:
        """
        Apply an event response to the bound instance.

        For GitMixin classes, uses the existing event machinery to properly
        copy the store, apply the event, update git history, and return a
        new instance with the change staged.
        """
        from edsl.store import create_event, apply_event

        event = create_event(response["event_name"], response["event_payload"])
        bound = self.bound_instance

        # Use existing GitMixin event machinery if available
        if hasattr(bound, "_wrap_event_method"):
            wrapped = bound._wrap_event_method(lambda: event)
            return wrapped()

        # Fallback for non-GitMixin classes: mutate in place
        if hasattr(bound.__class__, "_versioned"):
            store = getattr(bound, bound.__class__._versioned, None)
        elif hasattr(bound, "store"):
            store = bound.store
        else:
            store = None

        if store is None:
            raise RuntimeError(
                f"Cannot apply event to {type(bound).__name__}: no store found."
            )

        apply_event(event, store)
        return bound

    def __repr__(self) -> str:
        params = ", ".join(
            f"{name}: {info.get('type', 'Any')}"
            for name, info in self.parameters.items()
            if name != "instance"
        )
        instance_type = type(self.bound_instance).__name__
        return f"<InstanceMethodProxy {self.service_name}.{self.method_name}({params}) bound to {instance_type}>"


class InstanceServiceProxy:
    """
    Proxy for a remote service bound to a specific EDSL object instance.

    When methods are called, the bound instance is automatically serialized
    and sent as the 'instance' parameter for instance methods.
    """

    def __init__(self, client: ServiceClient, service_name: str, bound_instance: Any):
        self.client = client
        self.service_name = service_name
        self.bound_instance = bound_instance
        self._service_info: Optional[dict] = None
        self._method_proxies: Dict[str, InstanceMethodProxy] = {}

    @property
    def service_info(self) -> dict:
        """Lazy-load service info from API."""
        if self._service_info is None:
            self._service_info = self.client.get_service_info(self.service_name)
        return self._service_info

    @property
    def methods(self) -> List[str]:
        """List available method names."""
        return [m["method_name"] for m in self.service_info.get("methods", [])]

    def __getattr__(self, name: str) -> InstanceMethodProxy:
        """Get a method proxy by name."""
        # Check cache first
        if name in self._method_proxies:
            return self._method_proxies[name]

        # Find method info
        for method_info in self.service_info.get("methods", []):
            if method_info["method_name"] == name:
                proxy = InstanceMethodProxy(
                    self.client, self.service_name, method_info, self.bound_instance
                )
                self._method_proxies[name] = proxy
                return proxy

        raise AttributeError(
            f"Service '{self.service_name}' has no method '{name}'. "
            f"Available methods: {self.methods}"
        )

    def __repr__(self) -> str:
        instance_type = type(self.bound_instance).__name__
        return f"<InstanceServiceProxy '{self.service_name}' bound to {instance_type}>"

    def __dir__(self) -> List[str]:
        """Include available methods in dir() output."""
        return list(super().__dir__()) + self.methods


class ServiceEnabledMeta(type):
    """
    Metaclass that automatically enables filtered service access for any class.

    Services are only accessible if their `extends` field includes the class name.
    This allows creating service-enabled versions of EDSL classes with minimal code:

    Usage:
        from edsl.scenarios import ScenarioList as EDSLScenarioList

        class ScenarioList(EDSLScenarioList, metaclass=ServiceEnabledMeta):
            pass  # No other changes needed!

        # Now services that extend ScenarioList are automatically available
        sl = ScenarioList([...])
        result = sl.firecrawl.scrape(url="...")  # Works if firecrawl extends ScenarioList
    """

    _client: Optional[ServiceClient] = None
    _base_url: str = "http://localhost:8008"
    _service_cache: Dict[str, dict] = {}  # service_name -> service_info

    @classmethod
    def configure(mcs, base_url: str = "http://localhost:8008"):
        """
        Configure the API endpoint for all service-enabled classes.

        Args:
            base_url: Base URL of the service API
        """
        mcs._base_url = base_url
        mcs._client = None  # Reset to use new URL
        mcs._service_cache = {}  # Clear cache

    @classmethod
    def get_client(mcs) -> ServiceClient:
        """Get or create the shared service client."""
        if mcs._client is None:
            mcs._client = ServiceClient(mcs._base_url)
        return mcs._client

    @classmethod
    def _get_service_if_extends(
        mcs, service_name: str, class_name: str
    ) -> Optional[dict]:
        """
        Get service info if the service extends the given class.

        Args:
            service_name: Name of the service to check
            class_name: Name of the class to check against extends

        Returns:
            Service info dict if service extends class_name, None otherwise
        """
        # Check cache first
        if service_name in mcs._service_cache:
            service_info = mcs._service_cache[service_name]
            if service_info is None:
                return None
            if class_name in service_info.get("extends", []):
                return service_info
            return None

        # Try to fetch service info
        try:
            client = mcs.get_client()
            service_info = client.get_service_info(service_name)
            mcs._service_cache[service_name] = service_info

            if class_name in service_info.get("extends", []):
                return service_info
            return None
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                mcs._service_cache[service_name] = None  # Cache negative result
                return None
            raise
        except requests.exceptions.ConnectionError:
            return None

    def __new__(mcs, name: str, bases: tuple, namespace: dict):
        """
        Create a new class with service-aware __getattr__.

        Injects a __getattr__ method that checks if an attribute is a service
        that extends this class, and returns an InstanceServiceProxy if so.
        """
        # Capture any existing __getattr__ from the class or its bases
        original_getattr = namespace.get("__getattr__")

        # Also check bases for __getattr__ if not in namespace
        if original_getattr is None:
            for base in bases:
                if hasattr(base, "__getattr__"):
                    original_getattr = base.__getattr__
                    break

        def service_getattr(self, attr_name: str) -> Any:
            """
            Get attribute, checking for service access first.

            If attr_name is a service that extends this class, returns
            an InstanceServiceProxy. Otherwise falls back to original
            __getattr__ or raises AttributeError.
            """
            # Skip private attributes to avoid recursion
            if attr_name.startswith("_"):
                if original_getattr:
                    return original_getattr(self, attr_name)
                raise AttributeError(
                    f"'{type(self).__name__}' object has no attribute '{attr_name}'"
                )

            # Check if attr_name is a service that extends this class
            class_name = type(self).__name__
            service_info = mcs._get_service_if_extends(attr_name, class_name)

            if service_info is not None:
                # Return an InstanceServiceProxy bound to this instance
                return InstanceServiceProxy(mcs.get_client(), attr_name, self)

            # Fall back to original __getattr__ or raise AttributeError
            if original_getattr:
                return original_getattr(self, attr_name)
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{attr_name}'"
            )

        namespace["__getattr__"] = service_getattr

        return super().__new__(mcs, name, bases, namespace)

    @classmethod
    def get_available_services(mcs, class_name: str) -> List[str]:
        """
        Get list of services that extend a given class name.

        Args:
            class_name: The class name to filter by

        Returns:
            List of service names that extend the class
        """
        try:
            client = mcs.get_client()
            all_services = client.get_services()

            matching = []
            for service in all_services:
                svc_name = service["service_name"]
                if class_name in service.get("extends", []):
                    matching.append(svc_name)
                    # Cache the service info
                    if svc_name not in mcs._service_cache:
                        mcs._service_cache[svc_name] = service

            return matching
        except Exception:
            return []

    def __getattr__(cls, name: str) -> ServiceProxy:
        """
        Class-level attribute access for services.

        Enables `ScenarioList.firecrawl.scrape(...)` syntax for class methods
        (methods that don't require an instance).
        """
        # Skip dunder attributes to avoid recursion
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)

        # Check if this is a service that extends this class
        class_name = cls.__name__
        service_info = ServiceEnabledMeta._get_service_if_extends(name, class_name)

        if service_info is not None:
            return ServiceProxy(ServiceEnabledMeta.get_client(), name)

        raise AttributeError(f"type object '{class_name}' has no attribute '{name}'")

    def __dir__(cls) -> List[str]:
        """Include available services in dir() output."""
        base = list(super().__dir__())
        try:
            services = ServiceEnabledMeta.get_available_services(cls.__name__)
            return base + services
        except Exception:
            return base


class ScenarioListMockMeta(type):
    """
    Metaclass for ScenarioListMock that enables class-level attribute access.

    This allows `ScenarioListMock.firecrawl` to return a ServiceProxy
    without needing to instantiate ScenarioListMock.

    DEPRECATED: Use ServiceEnabledMeta instead for new classes.
    """

    _client: Optional[ServiceClient] = None
    _service_proxies: Dict[str, ServiceProxy] = {}
    _available_services: Optional[List[str]] = None

    def configure(cls, base_url: str = "http://localhost:8008"):
        """
        Configure the API endpoint.

        Args:
            base_url: Base URL of the service API
        """
        cls._client = ServiceClient(base_url)
        cls._service_proxies = {}
        cls._available_services = None

    @property
    def client(cls) -> ServiceClient:
        """Get or create the service client."""
        if cls._client is None:
            cls._client = ServiceClient()
        return cls._client

    @property
    def available_services(cls) -> List[str]:
        """List available service names from the API."""
        if cls._available_services is None:
            services = cls.client.get_services()
            cls._available_services = [s["service_name"] for s in services]
        return cls._available_services

    def __getattr__(cls, name: str) -> ServiceProxy:
        """Get a service proxy by name."""
        # Only skip true dunder attributes to avoid recursion
        # (e.g., __class__, __dict__), not single-underscore private methods
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)

        # Check cache first
        if name in cls._service_proxies:
            return cls._service_proxies[name]

        # Create new service proxy
        try:
            proxy = ServiceProxy(cls.client, name)
            # Validate the service exists by accessing its info
            _ = proxy.service_info
            cls._service_proxies[name] = proxy
            return proxy
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise AttributeError(
                    f"Service '{name}' not found. "
                    f"Available services: {cls.available_services}"
                )
            raise

    def __dir__(cls) -> List[str]:
        """Include available services in dir() output."""
        base = ["configure", "client", "available_services"]
        try:
            return base + cls.available_services
        except Exception:
            return base


class ScenarioListMock(metaclass=ScenarioListMockMeta):
    """
    Client for remote EDSL services.

    Provides both class-level and instance-level access to services.

    Usage:
        # Configure API endpoint (optional)
        ScenarioListMock.configure(base_url="http://localhost:8008")

        # Class-level: call service methods that return new data
        results = ScenarioListMock.firecrawl.scrape(url_or_urls="https://example.com")

        # Instance-level: call service methods on existing data
        sl = ScenarioListMock([{"name": "test"}])
        length = sl.firecrawl.length()  # Sends sl's data to server

        # List available services
        print(ScenarioListMock.available_services)  # ['firecrawl', ...]
    """

    def __init__(self, data: Any = None):
        """
        Initialize a ScenarioListMock with optional data.

        Args:
            data: The data to hold. Can be a list of dicts, a dict with
                  'scenarios' key, or any serializable data.
        """
        self._data = data if data is not None else []
        self._service_proxies: Dict[str, InstanceServiceProxy] = {}

    def to_dict(self) -> dict:
        """
        Serialize to a dict for transmission to the server.

        Returns a dict in the format expected by ScenarioList.from_dict().
        """
        if isinstance(self._data, dict) and "scenarios" in self._data:
            return self._data
        elif isinstance(self._data, list):
            # Wrap list in scenarios format
            return {
                "edsl_class_name": "ScenarioList",
                "scenarios": [
                    (
                        {"edsl_class_name": "Scenario", "data": item}
                        if isinstance(item, dict) and "data" not in item
                        else item
                    )
                    for item in self._data
                ],
            }
        else:
            return {
                "edsl_class_name": "ScenarioList",
                "scenarios": [],
                "data": self._data,
            }

    def __getattr__(self, name: str) -> InstanceServiceProxy:
        """
        Get a service proxy for instance-level method calls.

        This is called when accessing attributes that don't exist on the instance,
        allowing `sl.firecrawl.length()` to work.
        """
        # Avoid recursion for internal attributes
        if name.startswith("_"):
            raise AttributeError(name)

        # Check cache first
        if name in self._service_proxies:
            return self._service_proxies[name]

        # Get the client from the metaclass
        client = type(self).client

        # Try to create a service proxy
        try:
            proxy = InstanceServiceProxy(client, name, self)
            # Validate the service exists by accessing its info
            _ = proxy.service_info
            self._service_proxies[name] = proxy
            return proxy
        except Exception as e:
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'. "
                f"If '{name}' is a service, make sure the server is running."
            ) from e

    def __len__(self) -> int:
        """Return the number of items in the data."""
        if isinstance(self._data, list):
            return len(self._data)
        elif isinstance(self._data, dict) and "scenarios" in self._data:
            return len(self._data["scenarios"])
        return 0

    def __repr__(self) -> str:
        return f"ScenarioListMock({self._data!r})"

    def __iter__(self):
        """Iterate over the data items."""
        if isinstance(self._data, list):
            return iter(self._data)
        elif isinstance(self._data, dict) and "scenarios" in self._data:
            return iter(self._data["scenarios"])
        return iter([])


# Convenience aliases
Services = ScenarioListMock  # Legacy alias for backwards compatibility


class ServiceAccessor:
    """
    Descriptor that provides access to remote services from an EDSL instance.

    When accessed on an instance, returns an InstanceServiceProxy bound to
    that instance. When accessed on a class, raises AttributeError.

    Usage:
        # Add to a class
        class MyScenarioList(ScenarioList):
            firecrawl = ServiceAccessor("firecrawl")

        # Or use enable_services() to add dynamically
        enable_services(ScenarioList, ["firecrawl"])

        # Then use on instances
        sl = ScenarioList(...)
        length = sl.firecrawl.length()
    """

    _client: Optional[ServiceClient] = None
    _base_url: str = "http://localhost:8008"

    def __init__(self, service_name: str):
        self.service_name = service_name

    @classmethod
    def configure(cls, base_url: str = "http://localhost:8008"):
        """Configure the API endpoint for all service accessors."""
        cls._base_url = base_url
        cls._client = None  # Reset client to use new URL

    @classmethod
    def get_client(cls) -> ServiceClient:
        """Get or create the shared service client."""
        if cls._client is None:
            cls._client = ServiceClient(cls._base_url)
        return cls._client

    def __get__(self, obj, objtype=None) -> InstanceServiceProxy:
        if obj is None:
            raise AttributeError(
                f"Service '{self.service_name}' can only be accessed from instances, not the class"
            )
        return InstanceServiceProxy(self.get_client(), self.service_name, obj)

    def __repr__(self) -> str:
        return f"<ServiceAccessor '{self.service_name}'>"


class ServiceWrapper:
    """
    Wrapper that adds service access to any EDSL object instance.

    This is used by the with_services() function to provide service
    access without modifying the original class.
    """

    def __init__(self, wrapped_instance: Any, client: ServiceClient):
        # Store in __dict__ to avoid triggering __getattr__
        object.__setattr__(self, "_wrapped", wrapped_instance)
        object.__setattr__(self, "_client", client)
        object.__setattr__(self, "_service_proxies", {})

    def __getattr__(self, name: str) -> Any:
        wrapped = object.__getattribute__(self, "_wrapped")
        client = object.__getattribute__(self, "_client")
        proxies = object.__getattribute__(self, "_service_proxies")

        # Check if this is a service name
        try:
            services = client.get_services()
            service_names = [s["service_name"] for s in services]

            if name in service_names:
                if name not in proxies:
                    proxies[name] = InstanceServiceProxy(client, name, wrapped)
                return proxies[name]
        except Exception:
            pass

        # Otherwise delegate to the wrapped instance
        return getattr(wrapped, name)

    def __setattr__(self, name: str, value: Any):
        wrapped = object.__getattribute__(self, "_wrapped")
        setattr(wrapped, name, value)

    def __repr__(self) -> str:
        wrapped = object.__getattribute__(self, "_wrapped")
        return f"<ServiceWrapper wrapping {wrapped!r}>"

    def unwrap(self) -> Any:
        """Return the original wrapped instance."""
        return object.__getattribute__(self, "_wrapped")


def with_services(
    instance: Any, base_url: str = "http://localhost:8008"
) -> ServiceWrapper:
    """
    Wrap an EDSL instance to enable service access.

    This is useful when you want to call service methods on an instance
    without modifying the class definition.

    Args:
        instance: The EDSL object to wrap (e.g., a ScenarioList)
        base_url: The service API endpoint

    Returns:
        A ServiceWrapper that provides service access

    Usage:
        from edsl.scenarios import ScenarioList
        from service_client import with_services

        sl = ScenarioList([...])
        wrapped = with_services(sl)

        # Now you can call service methods
        length = wrapped.firecrawl.length()

        # Access original methods too
        print(wrapped.to_dict())

        # Get the original instance back
        original = wrapped.unwrap()
    """
    client = ServiceClient(base_url)
    return ServiceWrapper(instance, client)


def enable_services(
    cls: Type, service_names: List[str], base_url: str = "http://localhost:8008"
) -> Type:
    """
    Add service accessors to a class dynamically.

    This modifies the class to add ServiceAccessor descriptors for each
    service name, enabling instance-level service access.

    Args:
        cls: The class to modify (e.g., ScenarioList)
        service_names: List of service names to enable (e.g., ["firecrawl"])
        base_url: The service API endpoint

    Returns:
        The modified class (also modifies in place)

    Usage:
        from edsl.scenarios import ScenarioList
        from service_client import enable_services

        enable_services(ScenarioList, ["firecrawl"])

        # Now all ScenarioList instances can use services
        sl = ScenarioList([...])
        length = sl.firecrawl.length()
    """
    ServiceAccessor.configure(base_url)

    for service_name in service_names:
        setattr(cls, service_name, ServiceAccessor(service_name))

    return cls


# =============================================================================
# Service-Enabled EDSL Classes
# =============================================================================
# These classes use ServiceEnabledMeta to automatically provide access to
# remote services that declare they extend the corresponding EDSL type.


class ScenarioList(metaclass=ServiceEnabledMeta):
    """
    ScenarioList with automatic service access.

    A lightweight class that provides access to any remote service that
    declares `extends = ["ScenarioList"]`. Holds data that can be serialized
    and sent to remote services.

    Usage:
        from service_client import ScenarioList, ServiceEnabledMeta

        # Configure the service API endpoint (optional, defaults to localhost:8008)
        ServiceEnabledMeta.configure(base_url="http://localhost:8008")

        # Create a ScenarioList with data
        sl = ScenarioList([{"name": "test"}])

        # Access services that extend ScenarioList
        result = sl.firecrawl.scrape(url="https://example.com")

        # List available services for ScenarioList
        services = ServiceEnabledMeta.get_available_services("ScenarioList")
    """

    def __init__(self, data: Any = None):
        """
        Initialize a ScenarioList with optional data.

        Args:
            data: The data to hold. Can be a list of dicts, a dict with
                  'scenarios' key, or any serializable data.
        """
        self._data = data if data is not None else []

    def to_dict(self) -> dict:
        """
        Serialize to a dict for transmission to the server.

        Returns a dict in the format expected by ScenarioList.from_dict().
        """
        if isinstance(self._data, dict) and "scenarios" in self._data:
            return self._data
        elif isinstance(self._data, list):
            # Wrap list in scenarios format
            return {
                "edsl_class_name": "ScenarioList",
                "scenarios": [
                    (
                        {"edsl_class_name": "Scenario", "data": item}
                        if isinstance(item, dict) and "data" not in item
                        else item
                    )
                    for item in self._data
                ],
            }
        else:
            return {
                "edsl_class_name": "ScenarioList",
                "scenarios": [],
                "data": self._data,
            }

    @classmethod
    def from_list_of_dicts(cls, data: List[dict]) -> "ScenarioList":
        """Create a ScenarioList from a list of dictionaries."""
        return cls(data)

    def __len__(self) -> int:
        """Return the number of items in the data."""
        if isinstance(self._data, list):
            return len(self._data)
        elif isinstance(self._data, dict) and "scenarios" in self._data:
            return len(self._data["scenarios"])
        return 0

    def __repr__(self) -> str:
        return f"ScenarioList({self._data!r})"

    def __iter__(self):
        """Iterate over the data items."""
        if isinstance(self._data, list):
            return iter(self._data)
        elif isinstance(self._data, dict) and "scenarios" in self._data:
            return iter(self._data["scenarios"])
        return iter([])


class AgentList(metaclass=ServiceEnabledMeta):
    """
    AgentList with automatic service access.

    A lightweight class that provides access to any remote service that
    declares `extends = ["AgentList"]`.
    """

    def __init__(self, data: Any = None):
        """Initialize an AgentList with optional data."""
        self._data = data if data is not None else []

    def to_dict(self) -> dict:
        """Serialize to a dict for transmission to the server."""
        if isinstance(self._data, dict) and "agents" in self._data:
            return self._data
        elif isinstance(self._data, list):
            return {
                "edsl_class_name": "AgentList",
                "agents": [
                    (
                        {"edsl_class_name": "Agent", "traits": item}
                        if isinstance(item, dict) and "traits" not in item
                        else item
                    )
                    for item in self._data
                ],
            }
        else:
            return {"edsl_class_name": "AgentList", "agents": [], "data": self._data}

    @classmethod
    def from_list_of_dicts(cls, data: List[dict]) -> "AgentList":
        """Create an AgentList from a list of dictionaries."""
        return cls(data)

    def __len__(self) -> int:
        if isinstance(self._data, list):
            return len(self._data)
        elif isinstance(self._data, dict) and "agents" in self._data:
            return len(self._data["agents"])
        return 0

    def __repr__(self) -> str:
        return f"AgentList({self._data!r})"

    def __iter__(self):
        if isinstance(self._data, list):
            return iter(self._data)
        elif isinstance(self._data, dict) and "agents" in self._data:
            return iter(self._data["agents"])
        return iter([])


if __name__ == "__main__":
    # Demo usage
    print("EDSL Service Client")
    print("=" * 40)

    try:
        # Show available services for ScenarioList
        print("\n--- ServiceEnabledMeta Demo ---")
        available = ServiceEnabledMeta.get_available_services("ScenarioList")
        print(f"Services extending ScenarioList: {available}")

        print(f"\nScenarioList class: {ScenarioList}")
        print(f"Metaclass: {type(ScenarioList)}")

        # Create an instance and show available services
        sl = ScenarioList.from_list_of_dicts([{"test": "data"}])
        print(f"\nCreated: {sl}")

        # Try to access firecrawl service
        if "firecrawl" in available:
            print(f"\nFirecrawl service proxy: {sl.firecrawl}")

        # Also show legacy ScenarioListMock for backwards compatibility
        print("\n--- Legacy ScenarioListMock Demo ---")
        print(f"Available services: {ScenarioListMock.available_services}")
        print(f"Firecrawl service: {ScenarioListMock.firecrawl}")

    except requests.exceptions.ConnectionError:
        print("\nError: Could not connect to service API at http://localhost:8008")
        print("Make sure the server is running: uvicorn service_api:app --reload")

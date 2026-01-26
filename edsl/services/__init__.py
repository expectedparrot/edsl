"""
EDSL Services - Framework for creating and consuming external services.

This module provides infrastructure for:
1. Defining external services that extend EDSL types
2. Hosting services as REST APIs (requires fastapi)
3. Connecting to remote services as a client

Quick Start - Creating a Service:
    from edsl.services import ExternalService, method_type, MethodType
    from edsl.scenarios import ScenarioList

    class MyService(ExternalService):
        service_name = 'my_service'
        extends = [ScenarioList]

        @method_type(MethodType.CLASSMETHOD)
        def fetch_data(self, url: str) -> ScenarioList:
            '''Fetch data from URL.'''
            return ScenarioList.from_list_of_dicts([...])

Quick Start - Hosting a Service (requires fastapi):
    from edsl.services import ServiceAPI
    from my_service import MyService

    api = ServiceAPI()
    api.register_service(MyService)
    app = api.create_app()
    # Run with: uvicorn server:app

Quick Start - Using a Service (Client):
    from edsl.scenarios import ScenarioList

    # Configure endpoint
    from edsl.services import ServiceEnabledMeta
    ServiceEnabledMeta.configure(base_url="http://localhost:8008")

    # Discover available services
    services = ScenarioList.discover_services()

    # Use services
    sl = ScenarioList([...])
    result = sl.my_service.fetch_data(url="...")
"""

# Base classes and decorators for defining services
from edsl.services.external_service import (
    ExternalService,
    MethodType,
    method_type,
)

# Client-side connection infrastructure (always available)
from edsl.services.service_connector import (
    ServiceClient,
    ServiceEnabledMeta,
    ServiceProxy,
    InstanceServiceProxy,
    MethodProxy,
    InstanceMethodProxy,
    ServiceWrapper,
    ServiceAccessor,
    with_services,
    enable_services,
    serialize_param,
    deserialize_result,
)

# Client-side task polling (for background tasks)
from edsl.services.task_polling import (
    AdaptivePoller,
    poll_until_complete,
)

# Server-side hosting infrastructure (optional, requires fastapi)
# These are imported lazily to avoid requiring fastapi for client-only usage
_server_imports_available = False
try:
    from edsl.services.service_hosting import (
        ServiceAPI,
        create_app_from_services,
        get_service_info,
        to_serializable,
        deserialize_instance,
    )

    _server_imports_available = True
except ImportError:
    # FastAPI not installed - server-side hosting not available
    ServiceAPI = None
    create_app_from_services = None
    get_service_info = None
    to_serializable = None
    deserialize_instance = None


def _check_server_deps(name):
    """Raise helpful error if trying to use server features without fastapi."""
    if not _server_imports_available:
        raise ImportError(
            f"'{name}' requires fastapi. Install with: pip install fastapi uvicorn"
        )


__all__ = [
    # Service definition
    "ExternalService",
    "MethodType",
    "method_type",
    # Server hosting (optional)
    "ServiceAPI",
    "create_app_from_services",
    "get_service_info",
    "to_serializable",
    "deserialize_instance",
    # Client connection
    "ServiceClient",
    "ServiceEnabledMeta",
    "ServiceProxy",
    "InstanceServiceProxy",
    "MethodProxy",
    "InstanceMethodProxy",
    "ServiceWrapper",
    "ServiceAccessor",
    "with_services",
    "enable_services",
    "serialize_param",
    "deserialize_result",
    # Task polling (for background tasks)
    "AdaptivePoller",
    "poll_until_complete",
]

"""
External Services Framework for EDSL.

A general-purpose framework for dispatching work to external services via the
unified task queue. Services are pluggable, payloads are opaque, and any EDSL
component can use the framework.

Plugin Architecture
-------------------
Services can be installed from separate packages using Python entry points.
This allows:
    - Smaller edsl core package without service dependencies
    - Independent service versioning and updates
    - Third-party service packages (e.g., edsl-services-mycompany)

To use the standard service collection:
    pip install edsl-services
    
    # Or with specific dependencies:
    pip install edsl-services[firecrawl,exa]

Services register themselves via entry points in pyproject.toml:
    [project.entry-points."edsl.services"]
    myservice = "mypackage.services:MyService"

The unified task system supports:
    - External service tasks (embeddings, firecrawl, vibes, etc.)
    - LLM inference tasks (with dependencies)
    - Task groups and jobs for complex workflows

Core Components:
    - ServiceRegistry: Register and discover external services
    - ExternalService: Protocol for implementing services
    - KEYS: Standardized credential access for workers
    - PendingResult: Async result wrapper with polling/notification
    - dispatch: Main entry point for dispatching tasks to services
    - dispatch_group: Dispatch multiple related tasks with dependencies
    - set_default_server: Configure the RemoteServer for task dispatch
    - UnifiedWorker: Process tasks from the unified queue

Built-in Services:
    - exa: Exa web search and enrichment
    - firecrawl: Web scraping, crawling, and AI extraction
    - huggingface: Hugging Face dataset loading
    - embeddings: Text embedding generation
    - vibes: LLM-powered data transformations
    - And many more...

Example:
    >>> from edsl.services import dispatch, set_default_server
    >>> from edsl.store import InMemoryServer
    >>> 
    >>> # Configure server (required)
    >>> set_default_server(InMemoryServer())
    >>> 
    >>> # Dispatch to a service
    >>> pending = dispatch("exa", {"query": "AI researchers at Stanford"})
    >>> result = pending.result()  # Returns ScenarioList

Chaining tasks with dependencies:
    >>> from edsl.services import dispatch_group
    >>> 
    >>> # Create a chain of dependent tasks
    >>> group = dispatch_group([
    ...     {"service": "firecrawl", "params": {"url": "https://..."}},
    ...     {"service": "embeddings", "params": {...}, "dependencies": [0]},
    ... ])
    >>> results = group.wait()

Registering a new service:
    >>> from edsl.services import ServiceRegistry, ExternalService
    >>> 
    >>> @ServiceRegistry.register("myservice")
    >>> class MyService(ExternalService):
    ...     @classmethod
    ...     def create_task(cls, **kwargs) -> dict:
    ...         return kwargs
    ...     
    ...     @classmethod
    ...     def execute(cls, params: dict, keys: dict) -> dict:
    ...         # Called by worker
    ...         return {"rows": [...]}
    ...     
    ...     @classmethod
    ...     def parse_result(cls, result: dict):
    ...         from edsl.scenarios import ScenarioList
    ...         return ScenarioList.from_list_of_dicts(result["rows"])

Creating a custom service package:
    1. Create a new package with services inheriting from ExternalService
    2. Register entry points in pyproject.toml
    3. Users install your package: pip install my-edsl-services
    4. Services are automatically discovered and available
"""

from .base import ExternalService
from .registry import ServiceRegistry, ServiceMetadata, OperationSchema
from .keys import KEYS
from .pending import PendingResult
from .dispatcher import (
    dispatch,
    dispatch_group,
    TaskDispatcher,
    set_default_server,
    PendingGroup,
)
from .unified_worker import (
    UnifiedWorker,
    start_unified_worker,
    stop_all_workers,
    ensure_worker_for_types,
)
from .dependency_manager import DependencyManager, ensure_dependencies
from .accessor import ServiceAccessor, get_accessor
from .accessors import list_available_services, get_service_accessor

# Builtin services are loaded lazily when first accessed
# to avoid importing all ~100 service modules at startup
_builtin_loaded = False


def _ensure_builtin_services():
    """Load builtin services and discover entry point plugins.

    This function is called lazily when services are first accessed.
    It loads both:
    1. Builtin services from edsl/services/builtin/
    2. Plugin services registered via entry points (edsl.services group)

    Entry points allow external packages to register services:

        [project.entry-points."edsl.services"]
        myservice = "mypackage.services:MyService"
    """
    global _builtin_loaded
    if not _builtin_loaded:
        # Load builtin services first (they take precedence)
        from . import builtin  # noqa: F401

        # Discover entry point plugins
        ServiceRegistry._discover_entry_points()

        _builtin_loaded = True


__all__ = [
    # Core
    "ExternalService",
    "ServiceRegistry",
    "ServiceMetadata",
    "OperationSchema",
    "KEYS",
    "PendingResult",
    "PendingGroup",
    "dispatch",
    "dispatch_group",
    "TaskDispatcher",
    "set_default_server",
    # Dependency management
    "DependencyManager",
    "ensure_dependencies",
    # Dynamic accessors
    "ServiceAccessor",
    "get_accessor",
    "get_service_accessor",
    "list_available_services",
    # Unified worker
    "UnifiedWorker",
    "start_unified_worker",
    "stop_all_workers",
    "ensure_worker_for_types",
    # Builtin services
    "builtin",
]

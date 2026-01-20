"""
EDSL Services Runner - Discover and serve EDSL external services.

This module provides a server that automatically discovers and exposes
all installed EDSL services via REST APIs.

Quick Start - Run the server:
    python -m edsl.services_runner

    # With options
    python -m edsl.services_runner --port 8000 --reload

    # List available services
    python -m edsl.services_runner --list

Quick Start - Programmatic usage:
    from edsl.services_runner import create_app, run_server

    # Create FastAPI app (auto-discovers installed services)
    app = create_app()

    # Or run directly
    run_server(port=8000, reload=True)

Registering Services:
    Services are discovered via Python entry points. In your package's
    pyproject.toml:

    [project.entry-points."edsl.services"]
    my_service = "my_package.services:MyService"

    Or register manually:

    from edsl.services_runner import register_service
    from my_package import MyService

    register_service(MyService)
"""

# Registry functions
from edsl.services_runner.registry import (
    register_service,
    unregister_service,
    get_service,
    get_all_services,
    list_service_names,
    discover_services,
    get_registry,
    ServiceRegistry,
)

# Server functions (import lazily to avoid requiring fastapi)
def create_app(*args, **kwargs):
    """Create a FastAPI app exposing all registered services."""
    from edsl.services_runner.server import create_app as _create_app
    return _create_app(*args, **kwargs)


def run_server(*args, **kwargs):
    """Run the EDSL services server."""
    from edsl.services_runner.server import run_server as _run_server
    return _run_server(*args, **kwargs)


__all__ = [
    # Registry
    "register_service",
    "unregister_service",
    "get_service",
    "get_all_services",
    "list_service_names",
    "discover_services",
    "get_registry",
    "ServiceRegistry",
    # Server
    "create_app",
    "run_server",
]

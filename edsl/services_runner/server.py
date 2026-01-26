"""
EDSL Services Server - FastAPI server that exposes all registered services.

This module creates a FastAPI application that automatically discovers and
exposes all installed EDSL services via REST APIs.

Usage:
    # Start the server (discovers all installed services)
    python -m edsl.services_runner

    # Or programmatically
    from edsl.services_runner import create_app
    app = create_app()

    # Run with uvicorn
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""

import logging
import time
import uuid
from typing import List, Optional, Type

# Configure logging
logger = logging.getLogger("edsl.services")

from edsl.services_runner.registry import (
    get_all_services,
    get_all_services_with_types,
    discover_services,
    register_service,
)


def create_app(
    title: str = "EDSL Services API",
    version: str = "1.0.0",
    additional_services: Optional[List[Type]] = None,
    auto_discover: bool = True,
) -> "FastAPI":
    """
    Create a FastAPI application exposing all registered services.

    This function:
    1. Optionally discovers services from entry points
    2. Registers any additional services provided
    3. Creates a FastAPI app with endpoints for all services

    Args:
        title: API title for documentation
        version: API version
        additional_services: Optional list of service classes to register
        auto_discover: If True, discover services from entry points

    Returns:
        FastAPI application configured with all service endpoints

    Example:
        from edsl.services_runner import create_app
        from my_extension import MyService

        # Create app with auto-discovered services + custom ones
        app = create_app(additional_services=[MyService])

        # Run with uvicorn
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)
    """
    # Import here to make FastAPI optional until actually needed
    from fastapi import Request
    from starlette.middleware.base import BaseHTTPMiddleware
    from edsl.services.service_hosting import ServiceAPI

    # Discover services from entry points
    if auto_discover:
        discovered = discover_services()
        if discovered:
            print(f"Discovered services from entry points: {discovered}")

    # Register additional services
    if additional_services:
        for service_cls in additional_services:
            register_service(service_cls)
            print(f"Registered additional service: {service_cls.service_name}")

    # Get all registered services with type info
    all_services_with_types = get_all_services_with_types()

    if not all_services_with_types:
        print("Warning: No services registered. The API will be empty.")

    # Create the ServiceAPI and register all services
    api = ServiceAPI()

    # Track which services we've printed to avoid duplicates
    printed_services = set()

    for name, extends_type, service_cls in all_services_with_types:
        try:
            api.register_service(service_cls)

            # Only print once per service class
            if service_cls not in printed_services:
                extends = getattr(service_cls, "extends", [])
                extends_names = [t.__name__ if hasattr(t, "__name__") else str(t) for t in extends]
                desc = service_cls.__doc__.split(chr(10))[0] if service_cls.__doc__ else "No description"
                print(f"  - {name} (extends: {extends_names}): {desc}")
                printed_services.add(service_cls)
        except Exception as e:
            print(f"Warning: Failed to register service '{name}' for {extends_type}: {e}")

    # Create and return the FastAPI app
    app = api.create_app(title=title, version=version)

    # Add request logging middleware
    class RequestLoggingMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            request_id = str(uuid.uuid4())[:8]
            start_time = time.time()

            # Log incoming request
            logger.info(
                f"[{request_id}] --> {request.method} {request.url.path} "
                f"(client: {request.client.host if request.client else 'unknown'})"
            )

            try:
                response = await call_next(request)
                duration_ms = (time.time() - start_time) * 1000

                # Log response
                logger.info(
                    f"[{request_id}] <-- {response.status_code} "
                    f"({duration_ms:.1f}ms)"
                )
                return response
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                logger.error(
                    f"[{request_id}] <-- ERROR: {type(e).__name__}: {e} "
                    f"({duration_ms:.1f}ms)"
                )
                raise

    app.add_middleware(RequestLoggingMiddleware)

    # Add task dashboard
    try:
        from edsl.services_runner.dashboard import add_dashboard_routes

        add_dashboard_routes(app)
        print("  Dashboard available at: /dashboard")
    except Exception as e:
        print(f"  Dashboard not available: {e}")

    return app


def run_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
    title: str = "EDSL Services API",
    additional_services: Optional[List[Type]] = None,
    log_level: str = "INFO",
) -> None:
    """
    Run the EDSL services server.

    Args:
        host: Host to bind to
        port: Port to bind to
        reload: Enable auto-reload for development
        title: API title
        additional_services: Optional additional services to register
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)

    Example:
        from edsl.services_runner import run_server
        run_server(port=8000, reload=True)
    """
    import uvicorn

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper(), logging.INFO),
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    print("=" * 60)
    print(f"EDSL Services Server")
    print("=" * 60)
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Reload: {reload}")
    print(f"Log level: {log_level}")
    print()
    print("Discovering services...")

    # Create the app (this triggers discovery and registration)
    app = create_app(title=title, additional_services=additional_services)

    print()
    print(
        f"API Documentation: http://{host if host != '0.0.0.0' else 'localhost'}:{port}/docs"
    )
    print(
        f"OpenAPI Schema:    http://{host if host != '0.0.0.0' else 'localhost'}:{port}/openapi.json"
    )
    print("=" * 60)

    # Run with uvicorn
    # Note: We use uvicorn.Server directly instead of uvicorn.run() to avoid
    # compatibility issues with nest_asyncio, which patches asyncio.run() but
    # doesn't support the loop_factory argument that newer uvicorn versions use.
    if reload:
        # For reload mode, we need to pass the app as a string reference
        # This requires the app to be importable
        uvicorn.run(
            "edsl.services_runner.server:_app",
            host=host,
            port=port,
            reload=reload,
        )
    else:
        import asyncio

        config = uvicorn.Config(app, host=host, port=port)
        server = uvicorn.Server(config)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(server.serve())
        finally:
            loop.close()


# Module-level app for reload mode and direct uvicorn usage
# Created lazily on first access
_app = None


def get_app() -> "FastAPI":
    """Get or create the module-level app instance."""
    global _app
    if _app is None:
        _app = create_app()
    return _app


# For direct uvicorn usage: uvicorn edsl.services_runner.server:app
app = property(lambda self: get_app())


# Create app when module is imported for uvicorn compatibility
def _init_app():
    """Initialize app for uvicorn module loading."""
    global _app
    if _app is None:
        _app = create_app()
    return _app

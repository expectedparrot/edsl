"""
EDSL Extensions Module

This module provides functionality for:
1. Interacting with the Extension Gateway API for calling existing services
2. Creating new EDSL services without FastAPI knowledge using the service framework

Gateway client and extension interface are lazily imported to avoid loading httpx at import time.
"""

# Lazy imports for all components to avoid loading httpx/uvicorn at import time
def __getattr__(name):
    """Lazy import for extension components to avoid heavy dependencies at import time."""
    # Gateway client components (requires httpx)
    if name in ["ExtensionGatewayClient", "call_service", "list_services", "create_service"]:
        from .gateway_client import (
            ExtensionGatewayClient,
            call_service,
            list_services,
            create_service,
        )
        globals().update({
            "ExtensionGatewayClient": ExtensionGatewayClient,
            "call_service": call_service,
            "list_services": list_services,
            "create_service": create_service,
        })
        return globals()[name]

    # Extension interface components
    if name in ["ExtensionManager", "Extensions", "ExtensionService", "extension", "extensions"]:
        from .extension_interface import (
            ExtensionManager,
            Extensions,
            ExtensionService,
            extension,
            extensions,
        )
        globals().update({
            "ExtensionManager": ExtensionManager,
            "Extensions": Extensions,
            "ExtensionService": ExtensionService,
            "extension": extension,
            "extensions": extensions,
        })
        return globals()[name]

    # Service framework components (requires uvicorn)
    if name in [
        "edsl_service",
        "input_param",
        "output_schema",
        "run_service",
        "validate_service",
        "generate_service_files",
        "ServiceFrameworkException",
    ]:
        try:
            from .service_framework import (
                edsl_service,
                input_param,
                output_schema,
                run_service,
                validate_service,
                generate_service_files,
                ServiceFrameworkException,
            )

            globals().update(
                {
                    "edsl_service": edsl_service,
                    "input_param": input_param,
                    "output_schema": output_schema,
                    "run_service": run_service,
                    "validate_service": validate_service,
                    "generate_service_files": generate_service_files,
                    "ServiceFrameworkException": ServiceFrameworkException,
                }
            )
            return globals()[name]
        except ImportError as e:
            raise ImportError(
                f"Service framework component '{name}' requires uvicorn. "
                f"Install with: pip install 'edsl[services]' or pip install fastapi uvicorn. "
                f"Original error: {e}"
            )
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


__all__ = [
    # Gateway client for calling services
    "ExtensionGatewayClient",
    "call_service",
    "list_services",
    "create_service",
    # Extension interface
    "ExtensionManager",
    "Extensions",
    "ExtensionService",
    "extension",
    "extensions",
    # Service framework (lazy loaded)
    "edsl_service",
    "input_param",
    "output_schema",
    "run_service",
    "validate_service",
    "generate_service_files",
    "ServiceFrameworkException",
]

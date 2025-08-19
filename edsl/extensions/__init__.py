"""
EDSL Extensions Module

This module provides functionality for:
1. Interacting with the Extension Gateway API for calling existing services
2. Creating new EDSL services without FastAPI knowledge using the service framework
"""

# Core extension functionality - no heavy dependencies
from .gateway_client import (
    ExtensionGatewayClient,
    call_service,
    list_services,
    create_service,
)

from .extension_interface import (
    ExtensionManager,
    Extensions,
    ExtensionService,
    extension,
    extensions,
)


# Service framework imports - only available if uvicorn is installed
def __getattr__(name):
    """Lazy import for service framework components to avoid uvicorn dependency for basic extensions"""
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

"""
EDSL Extensions Module

This module provides functionality for:
1. Interacting with the Extension Gateway API for calling existing services
2. Creating new EDSL services without FastAPI knowledge using the service framework
"""

from .gateway_client import (
    ExtensionGatewayClient,
    call_service,
    list_services,
    create_service,
)

from .service_framework import (
    edsl_service,
    input_param,
    output_schema,
    run_service,
    validate_service,
    generate_service_files,
    ServiceFrameworkException,
)

__all__ = [
    # Gateway client for calling services
    "ExtensionGatewayClient",
    "call_service",
    "list_services",
    "create_service",
    # Service framework for creating services
    "edsl_service",
    "input_param",
    "output_schema",
    "run_service",
    "validate_service",
    "generate_service_files",
    "ServiceFrameworkException",
]

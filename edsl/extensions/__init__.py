"""
EDSL Extensions Module

This module provides functionality for interacting with the Extension Gateway API
for registering, listing, and calling FastAPI services.
"""

from .gateway_client import (
    ExtensionGatewayClient,
    call_service,
    list_services,
    create_service,
)

__all__ = ["ExtensionGatewayClient", "call_service", "list_services", "create_service"]

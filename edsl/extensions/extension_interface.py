"""
Extension Interface Module

Provides a dictionary-like interface for calling extension services:
extension["extension_name"].method_name(param1=value, param2=value2)
"""

import os
import httpx
from typing import Dict, Any, Optional
from .gateway_client import ExtensionGatewayClient


class ExtensionService:
    """Represents a specific extension service that can have methods called on it."""

    def __init__(self, service_name: str, gateway_client: ExtensionGatewayClient):
        self.service_name = service_name
        self.gateway_client = gateway_client
        self._service_info = None

    def _get_service_info(self) -> Dict[str, Any]:
        """Get service information including available endpoints."""
        if self._service_info is None:
            services = self.gateway_client.list_services()
            for service in services.get("services", []):
                if service.get("name") == self.service_name:
                    self._service_info = service
                    break
            if self._service_info is None:
                raise ValueError(f"Service '{self.service_name}' not found")
        return self._service_info

    def call_service(
        self,
        path: str,
        method: str = "POST",
        json_data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        token: Optional[str] = None,
        **kwargs,
    ):
        """
        Call the service with the given path and parameters.
        This provides backward compatibility with existing code.
        """
        if token is None:
            token = kwargs.pop(
                "ep_api_token", os.environ.get("EXPECTED_PARROT_API_KEY")
            )
        if not token:
            raise ValueError(
                "ep_api_token is required. Provide it as a parameter or set EXPECTED_PARROT_API_KEY environment variable."
            )

        response = self.gateway_client.call_service(
            service_name=self.service_name,
            path=path,
            token=token,
            method=method,
            json_data=json_data,
            params=params,
        )

        try:
            return response.json()
        except Exception:
            return response.text

    def __getattr__(self, method_name: str):
        """
        Allow calling methods on the service object using the syntax:
        extension["extension_name"].method_name(param1=value, param2=value2)

        The method_name is converted to path by replacing underscores with hyphens.
        All parameters become the POST request body.
        """

        def service_method(**kwargs):
            # Get the EP token from kwargs or environment
            token = kwargs.pop(
                "ep_api_token", os.environ.get("EXPECTED_PARROT_API_KEY")
            )
            if not token:
                raise ValueError(
                    "ep_api_token is required. Provide it as a parameter or set EXPECTED_PARROT_API_KEY environment variable."
                )

            # Convert method name to path: underscore to hyphen
            path = method_name.replace("_", "-")

            # All parameters go in the POST request body
            response = self.gateway_client.call_service(
                service_name=self.service_name,
                path=path,
                token=token,
                method="POST",
                json_data=kwargs,
            )

            # Return the JSON response
            try:
                return response.json()
            except Exception:
                return response.text

        return service_method

    def __repr__(self):
        return f"ExtensionService('{self.service_name}')"


class ExtensionManager:
    """
    Dictionary-like interface for accessing extension services.

    Usage:
        extension["service_name"].method_name(param1=value, param2=value)
        or
        extension["service_name"].call_service(path="...", method="POST", json_data={...})
    """

    def __init__(self, gateway_url: Optional[str] = None):
        self.gateway_client = ExtensionGatewayClient(gateway_url=gateway_url)
        self._services_cache = {}

    def __getitem__(self, service_name: str) -> ExtensionService:
        """Get a service by name, returning an ExtensionService object."""
        if service_name not in self._services_cache:
            self._services_cache[service_name] = ExtensionService(
                service_name, self.gateway_client
            )
        return self._services_cache[service_name]

    def __contains__(self, service_name: str) -> bool:
        """Check if a service exists."""
        try:
            services = self.gateway_client.list_services()
            service_names = [s.get("name") for s in services.get("services", [])]
            return service_name in service_names
        except Exception:
            return False

    def get_service(self, service_name: str) -> ExtensionService:
        """Get a service by name (alternative to bracket notation)."""
        return self[service_name]

    def list_services(self) -> list:
        """List all available services (backward compatibility)."""
        try:
            services_response = self.gateway_client.list_services()
            return services_response.get("services", [])
        except Exception:
            return []

    def list_available_services(self) -> Dict[str, Any]:
        """List all available services."""
        return self.gateway_client.list_services()

    def list(self):
        """Print the available extension names."""
        try:
            services_response = self.gateway_client.list_services()
            services = services_response.get("services", [])
            if not services:
                print("No extensions available")
                return

            print("Available extensions:")
            for service in services:
                service_name = service.get("service_name", "Unknown")
                description = service.get("description", "No description")
                cost_credits = service.get("cost_credits", "Unknown")
                ep_username = service.get("ep_username", "Unknown")
                print(
                    f"  - {service_name}: {description} (Cost: {cost_credits} credits, Owner: {ep_username})"
                )

        except Exception as e:
            print(f"Error listing extensions: {e}")

    def __repr__(self):
        return "ExtensionManager()"


# Alias for backward compatibility
Extensions = ExtensionManager

# Create default instances that users can import
extension = ExtensionManager()
extensions = ExtensionManager()

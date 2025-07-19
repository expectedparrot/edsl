"""
Extension Gateway Client

This module provides functions to interact with the Extension Gateway API
for registering, listing, and calling FastAPI services.
"""

import os
import httpx
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin


class ExtensionGatewayClient:
    """Client for interacting with the Extension Gateway API"""

    def __init__(self, gateway_url: Optional[str] = None, timeout: float = 300.0):
        """
        Initialize the Extension Gateway client.

        Args:
            gateway_url: Base URL of the Extension Gateway. If not provided,
                        will use EDSL_EXTENSION_GATEWAY_URL env var or default to http://localhost:8000
            timeout: Request timeout in seconds
        """
        if gateway_url is None:
            gateway_url = os.getenv(
                "EDSL_EXTENSION_GATEWAY_URL", "http://localhost:8000"
            )
        self.gateway_url = gateway_url.rstrip("/")
        self.timeout = timeout

    def list_services(self, ep_username: Optional[str] = None) -> Dict[str, Any]:
        """
        List all registered services or filter by username.

        Args:
            ep_username: Optional username to filter services by owner

        Returns:
            Dictionary containing list of services and total count

        Raises:
            httpx.HTTPError: If the request fails
        """
        params = {}
        if ep_username:
            params["ep_username"] = ep_username

        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.gateway_url}/services", params=params)
            response.raise_for_status()
            return response.json()

    def create_service(
        self,
        service_name: str,
        service_url: str,
        ep_username: str,
        description: Optional[str] = None,
        cost_credits: int = 1,
        uses_user_account: bool = True,
        example_script: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Register a new service with the gateway.

        Args:
            service_name: Unique name for the service
            service_url: URL where the service is hosted
            ep_username: Username of the service owner
            description: Optional description of the service
            cost_credits: Credits charged per service call (defaults to 1)
            uses_user_account: Whether service uses caller's EP account (defaults to True)
            example_script: Optional Python example script showing how to use the service

        Returns:
            Dictionary containing the registered service details

        Raises:
            httpx.HTTPError: If the request fails
            ValueError: If service is already registered or URL validation fails
        """
        payload = {
            "service_name": service_name,
            "service_url": service_url,
            "cost_credits": cost_credits,
            "uses_user_account": uses_user_account,
        }
        if description:
            payload["description"] = description
        if example_script:
            payload["example_script"] = example_script

        headers = {"ep-username": ep_username, "Content-Type": "application/json"}

        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                f"{self.gateway_url}/register", json=payload, headers=headers
            )

            if response.status_code == 400:
                error_detail = response.json().get("detail", "Bad request")
                raise ValueError(f"Registration failed: {error_detail}")

            response.raise_for_status()
            return response.json()

    def call_service(
        self,
        service_name: str,
        path: str,
        token: str,
        method: str = "GET",
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> httpx.Response:
        """
        Call a registered service through the gateway.

        Args:
            service_name: Name of the registered service
            path: Path to call on the service (without leading slash)
            token: Authorization bearer token
            method: HTTP method (GET, POST, etc.)
            params: Optional query parameters
            json_data: Optional JSON data for POST/PUT requests
            headers: Optional additional headers

        Returns:
            httpx.Response object from the service

        Raises:
            httpx.HTTPError: If the request fails
            ValueError: If service is not found or authorization fails
        """
        # Build the full URL
        call_url = f"{self.gateway_url}/call/{service_name}/{path}"

        # Set up headers
        request_headers = {"Authorization": f"Bearer {token}"}
        if headers:
            request_headers.update(headers)

        # Make the request
        with httpx.Client(timeout=self.timeout) as client:
            response = client.request(
                method=method,
                url=call_url,
                params=params,
                json=json_data,
                headers=request_headers,
            )

            if response.status_code == 404:
                raise ValueError(f"Service '{service_name}' not found")
            elif response.status_code == 401:
                raise ValueError("Authorization token required or invalid")

            response.raise_for_status()
            return response

    def get_service_openapi(self, service_name: str) -> Dict[str, Any]:
        """
        Get the OpenAPI specification for a registered service.

        Args:
            service_name: Name of the registered service

        Returns:
            Dictionary containing the OpenAPI specification

        Raises:
            httpx.HTTPError: If the request fails
            ValueError: If service is not found
        """
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(f"{self.gateway_url}/openapi/{service_name}")

            if response.status_code == 404:
                raise ValueError(f"Service '{service_name}' not found")

            response.raise_for_status()
            return response.json()

    def delete_service(self, service_name: str, ep_username: str) -> Dict[str, Any]:
        """
        Unregister a service from the gateway.

        Args:
            service_name: Name of the service to delete
            ep_username: Username of the service owner

        Returns:
            Dictionary with success message

        Raises:
            httpx.HTTPError: If the request fails
            ValueError: If service not found or user lacks permission
        """
        headers = {"ep-username": ep_username}

        with httpx.Client(timeout=self.timeout) as client:
            response = client.delete(
                f"{self.gateway_url}/services/{service_name}", headers=headers
            )

            if response.status_code == 404:
                raise ValueError(f"Service '{service_name}' not found")
            elif response.status_code == 403:
                raise ValueError("You don't have permission to unregister this service")

            response.raise_for_status()
            return response.json()


# Convenience functions for direct usage


def list_services(
    gateway_url: Optional[str] = None, ep_username: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    List all registered services.

    Args:
        gateway_url: Base URL of the Extension Gateway. If not provided,
                    will use EDSL_EXTENSION_GATEWAY_URL env var or default to http://localhost:8000
        ep_username: Optional username to filter services

    Returns:
        List of service dictionaries
    """
    client = ExtensionGatewayClient(gateway_url)
    result = client.list_services(ep_username)

    for service in result.get("services", []):
        service["service_docs_url"] = urljoin(
            client.gateway_url, f"/service/{service['service_name']}"
        )
    return result["services"]


def create_service(
    service_name: str,
    service_url: str,
    ep_username: str,
    description: Optional[str] = None,
    cost_credits: int = 1,
    uses_user_account: bool = True,
    example_script: Optional[str] = None,
    gateway_url: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Register a new service with the gateway.

    Args:
        service_name: Unique name for the service
        service_url: URL where the service is hosted
        ep_username: Username of the service owner
        description: Optional description of the service
        cost_credits: Credits charged per service call (defaults to 1)
        uses_user_account: Whether service uses caller's EP account (defaults to True)
        example_script: Optional Python example script showing how to use the service
        gateway_url: Base URL of the Extension Gateway. If not provided,
                    will use EDSL_EXTENSION_GATEWAY_URL env var or default to http://localhost:8000

    Returns:
        Dictionary containing the registered service details
    """
    client = ExtensionGatewayClient(gateway_url)
    return client.create_service(
        service_name,
        service_url,
        ep_username,
        description,
        cost_credits,
        uses_user_account,
        example_script,
    )


def call_service(
    service_name: str,
    path: str,
    token: str = os.environ.get("EXPECTED_PARROT_API_KEY", None),
    method: str = "GET",
    params: Optional[Dict[str, Any]] = None,
    json_data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    gateway_url: Optional[str] = None,
) -> Any:
    """
    Call a registered service through the gateway.

    Args:
        service_name: Name of the registered service
        path: Path to call on the service
        token: Authorization bearer token
        method: HTTP method
        params: Optional query parameters
        json_data: Optional JSON data for POST/PUT requests
        headers: Optional additional headers
        gateway_url: Base URL of the Extension Gateway. If not provided,
                    will use EDSL_EXTENSION_GATEWAY_URL env var or default to http://localhost:8000

    Returns:
        Response data from the service (JSON or text)
    """
    client = ExtensionGatewayClient(gateway_url)
    response = client.call_service(
        service_name, path, token, method, params, json_data, headers
    )

    # Try to return JSON, otherwise return text
    try:
        return response.json()
    except:
        return response.text

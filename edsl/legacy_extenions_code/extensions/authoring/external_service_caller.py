import requests
import logging
from typing import Dict, Any, Optional
from .exceptions import ServiceConnectionError, ServiceResponseError

logger = logging.getLogger(__name__)


class ExternalServiceCaller:
    """Handles HTTP requests to external service endpoints."""

    def __init__(self, timeout: int = 120):
        self.timeout = timeout

    def call_service(
        self, service_def, params: Dict[str, Any], ep_api_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Call an external service endpoint with the provided parameters.

        Args:
            service_def: ServiceDefinition instance containing endpoint and metadata
            params: Parameters to send to the service
            ep_api_token: Optional API token for authorization

        Returns:
            Dict[str, Any]: JSON response from the service

        Raises:
            ServiceConnectionError: If the request fails due to network issues
            ServiceResponseError: If the service returns an error status
        """
        endpoint = service_def.service_endpoint
        headers = {"Content-Type": "application/json"}

        if ep_api_token:
            headers["Authorization"] = f"Bearer {ep_api_token}"

        logger.debug(
            "Sending request to external endpoint %s | Headers: %s | Payload: %s",
            endpoint,
            headers,
            params,
        )

        try:
            response = requests.post(
                endpoint, json=params, headers=headers, timeout=self.timeout
            )

            logger.debug(
                "Received response from %s | Status: %s", endpoint, response.status_code
            )

            if response.status_code >= 400:
                try:
                    error_detail = response.json()
                except Exception:
                    error_detail = response.text

                logger.error(
                    "External service responded with non-success status | service=%s | endpoint=%s | status=%s | detail=%s",
                    service_def.service_name,
                    endpoint,
                    response.status_code,
                    error_detail,
                )

                raise ServiceResponseError(
                    f"External service '{service_def.service_name}' failed with status {response.status_code}: {error_detail}"
                )

            return response.json()

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            logger.error(
                "External service request failed for %s at %s: %s",
                service_def.service_name,
                endpoint,
                e,
            )
            raise ServiceConnectionError(
                f"Error connecting to external service '{service_def.service_name}': {str(e)}"
            ) from e
        except requests.exceptions.RequestException as e:
            logger.error(
                "Unexpected error calling external service %s at %s: %s",
                service_def.service_name,
                endpoint,
                e,
            )
            raise ServiceConnectionError(
                f"Unexpected error calling external service '{service_def.service_name}': {str(e)}"
            ) from e


class AsyncExternalServiceCaller:
    """Async version for use in FastAPI applications like the gateway."""

    def __init__(self, http_client, timeout: int = 120):
        """
        Args:
            http_client: httpx.AsyncClient instance
            timeout: Request timeout in seconds
        """
        self.http_client = http_client
        self.timeout = timeout

    async def call_service(
        self, service_def, params: Dict[str, Any], ep_api_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Async version of call_service for use in FastAPI applications.

        Args:
            service_def: ServiceDefinition instance containing endpoint and metadata
            params: Parameters to send to the service
            ep_api_token: Optional API token for authorization

        Returns:
            Dict[str, Any]: JSON response from the service

        Raises:
            ServiceConnectionError: If the request fails due to network issues
            ServiceResponseError: If the service returns an error status
        """
        endpoint = service_def.service_endpoint
        headers = {"Content-Type": "application/json"}

        if ep_api_token:
            headers["Authorization"] = f"Bearer {ep_api_token}"

        logger.debug(
            "Sending async request to external endpoint %s | Headers: %s | Payload: %s",
            endpoint,
            headers,
            params,
        )

        try:
            response = await self.http_client.post(
                endpoint, json=params, headers=headers
            )

            logger.debug(
                "Received response from %s | Status: %s", endpoint, response.status_code
            )

            if response.status_code >= 400:
                try:
                    error_detail = response.json()
                except Exception:
                    error_detail = response.text

                logger.error(
                    "External service responded with non-success status | service=%s | endpoint=%s | status=%s | detail=%s",
                    service_def.service_name,
                    endpoint,
                    response.status_code,
                    error_detail,
                )

                # Convert to FastAPI HTTPException for gateway compatibility
                try:
                    from fastapi import HTTPException

                    raise HTTPException(
                        status_code=response.status_code, detail=error_detail
                    )
                except ImportError:
                    # Fall back to our custom exception if FastAPI not available
                    raise ServiceResponseError(
                        f"External service '{service_def.service_name}' failed with status {response.status_code}: {error_detail}"
                    )

            return response.json()

        except Exception as e:
            # Handle httpx-specific exceptions and convert to appropriate errors
            if "httpx" in str(type(e)) and "RequestError" in str(type(e)):
                logger.error(
                    "External service request failed for %s at %s: %s",
                    service_def.service_name,
                    endpoint,
                    e,
                )
                # Convert to FastAPI HTTPException for gateway compatibility
                try:
                    from fastapi import HTTPException

                    raise HTTPException(
                        status_code=503,
                        detail=f"Error connecting to external service '{service_def.service_name}': {str(e)}",
                    ) from e
                except ImportError:
                    # Fall back to our custom exception if FastAPI not available
                    raise ServiceConnectionError(
                        f"Error connecting to external service '{service_def.service_name}': {str(e)}"
                    ) from e
            else:
                logger.exception(
                    "Error processing response from external service '%s'",
                    service_def.service_name,
                )
                # Convert to FastAPI HTTPException for gateway compatibility
                try:
                    from fastapi import HTTPException

                    raise HTTPException(
                        status_code=500,
                        detail=f"Error processing response from external service '{service_def.service_name}': {str(e)}",
                    ) from e
                except ImportError:
                    # Fall back to our custom exception if FastAPI not available
                    raise ServiceResponseError(
                        f"Error processing response from external service '{service_def.service_name}': {str(e)}"
                    ) from e

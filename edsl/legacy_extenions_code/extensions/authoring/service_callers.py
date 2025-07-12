import sys
import threading
import itertools
import time
import logging
import requests
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass
from abc import ABC, abstractmethod

from .exceptions import (
    ServiceConnectionError,
    ServiceResponseError,
    ServiceConfigurationError,
    ServiceDeserializationError,
)

logger = logging.getLogger(__name__)

TIMEOUT = 240


class ProgressSpinner:
    """Lightweight console spinner that also shows elapsed seconds."""

    def __init__(self, message: str, delay: float = 0.1):
        self.message = message.rstrip()
        self.delay = delay
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

    def _spin(self):
        spinner_chars = itertools.cycle("|/-\\")
        start = time.time()
        while not self._stop_event.is_set():
            char = next(spinner_chars)
            elapsed = time.time() - start
            sys.stdout.write(f"\r{self.message} {char} {elapsed:.1f}s")
            sys.stdout.flush()
            time.sleep(self.delay)
        # Clear line and print final time
        elapsed = time.time() - start
        sys.stdout.write(f"\r{self.message} done in {elapsed:.2f}s\n")
        sys.stdout.flush()

    def start(self):
        if sys.stdout.isatty():
            self._thread.start()

    def stop(self):
        if sys.stdout.isatty():
            self._stop_event.set()
            self._thread.join()


class BaseServiceCaller(ABC):
    """Abstract base class for service callers."""

    def __init__(
        self,
        service_name: str,
        ep_api_token: Optional[str] = None,
        timeout: int = TIMEOUT,
    ):
        self.service_name = service_name
        self.ep_api_token = ep_api_token
        self.timeout = timeout

    @abstractmethod
    def call_service(
        self, prepared_params: Dict[str, Any], deserialize_response: Callable
    ) -> Any:
        """Call the service and return the deserialized response."""
        pass


@dataclass
class GatewayServiceCaller(BaseServiceCaller):
    """Handles API calls through the gateway."""

    def __init__(
        self,
        service_name: str,
        gateway_url: str,
        ep_api_token: Optional[str] = None,
        timeout: int = TIMEOUT,
    ):
        super().__init__(service_name, ep_api_token, timeout)
        self.gateway_url = gateway_url.rstrip("/")

    def _make_api_call(self, payload: Dict[str, Any]) -> requests.Response:
        """Makes the API request to the gateway and returns the response object."""
        url = f"{self.gateway_url}/service/"

        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()  # Raises HTTPError for 4xx/5xx
            return response
        except requests.exceptions.HTTPError as e:
            # Raise ServiceResponseError for bad status codes
            error_message = f"Error calling service '{self.service_name}' at {url}. Server returned status {e.response.status_code}."
            try:
                error_message += f" Response: {e.response.text}"
            except Exception:
                error_message += " Response content could not be read."
            logger.error(error_message)
            raise ServiceResponseError(error_message) from e
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            # Raise ServiceConnectionError for connection issues
            error_message = (
                f"Error connecting to service '{self.service_name}' at {url}: {e}"
            )
            logger.error(error_message)
            raise ServiceConnectionError(error_message) from e
        except requests.exceptions.RequestException as e:
            # Catch other potential request errors
            error_message = (
                f"Error during request for service '{self.service_name}' at {url}: {e}"
            )
            if hasattr(e, "response") and e.response is not None:
                error_message += f"\nResponse status: {e.response.status_code}"
                try:
                    error_message += f"\nResponse content: {e.response.text}"
                except Exception:
                    error_message += "\nResponse content could not be read."
            logger.error(error_message)
            raise ServiceConnectionError(error_message) from e

    def call_service(
        self, prepared_params: Dict[str, Any], deserialize_response: Callable
    ) -> Any:
        """
        Makes a service call through the gateway with progress reporting.

        Args:
            prepared_params: The prepared parameters for the service call
            deserialize_response: Function to deserialize the response

        Returns:
            The deserialized response from the service

        Raises:
            ServiceConfigurationError: If gateway_url is not set
            ServiceConnectionError: If the API call fails due to connection issues
            ServiceResponseError: If the API call returns an error status or invalid JSON
            ServiceDeserializationError: If the response cannot be deserialized correctly
        """
        if not self.gateway_url:
            raise ServiceConfigurationError(
                f"Service '{self.service_name}' cannot be called. Configuration missing (gateway_url)."
            )

        # Construct the gateway payload
        payload = {"service": self.service_name, "params": prepared_params}
        if self.ep_api_token:
            payload["ep_api_token"] = self.ep_api_token

        # Display progress spinner
        logger.info("Calling service '%s' via gateway...", self.service_name)
        spinner = ProgressSpinner(
            message=f"Calling service '{self.service_name}' via gateway"
        )

        spinner.start()
        try:
            response = self._make_api_call(payload)
            return deserialize_response(response)
        finally:
            spinner.stop()


@dataclass
class DirectServiceCaller(BaseServiceCaller):
    """Handles direct API calls to service endpoints using centralized external service logic."""

    def __init__(
        self,
        service_name: str,
        service_endpoint: str,
        ep_api_token: Optional[str] = None,
        timeout: int = 120,
    ):
        super().__init__(service_name, ep_api_token, timeout)
        self.service_endpoint = service_endpoint.rstrip("/")
        # Import here to avoid circular imports
        from .external_service_caller import ExternalServiceCaller

        self.external_caller = ExternalServiceCaller(timeout=timeout)

    def call_service(
        self, prepared_params: Dict[str, Any], deserialize_response: Callable
    ) -> Any:
        """
        Makes a direct service call to the service endpoint using the same logic as the gateway.

        Args:
            prepared_params: The prepared parameters for the service call (with EDSL objects serialized as dicts)
            deserialize_response: Function to deserialize the response

        Returns:
            The deserialized response from the service

        Raises:
            ServiceConfigurationError: If service_endpoint is not set
            ServiceConnectionError: If the API call fails due to connection issues
            ServiceResponseError: If the API call returns an error status or invalid JSON
            ServiceDeserializationError: If the response cannot be deserialized correctly
        """
        if not self.service_endpoint:
            raise ServiceConfigurationError(
                f"Service '{self.service_name}' has no endpoint defined – cannot call directly."
            )

        # Create a minimal service definition object for the external caller
        class ServiceDef:
            def __init__(self, name, endpoint):
                self.service_name = name
                self.service_endpoint = endpoint

        service_def = ServiceDef(self.service_name, self.service_endpoint)

        logger.info(
            "Calling service '%s' directly at %s...",
            self.service_name,
            self.service_endpoint,
        )

        # Use the same external service calling logic as the gateway
        # Send serialized dicts via HTTP - the FastAPI endpoint will deserialize them
        response_data = self.external_caller.call_service(
            service_def=service_def,
            params=prepared_params,  # Send serialized dicts (JSON-compatible)
            ep_api_token=self.ep_api_token,
        )

        # Create a mock response object for the deserialize_response function
        class MockResponse:
            def __init__(self, data):
                self._data = data

            def json(self):
                return self._data

        mock_response = MockResponse(response_data)
        return deserialize_response(mock_response)

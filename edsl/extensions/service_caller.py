import sys
import threading
import itertools
import time
import logging
import requests
from typing import Dict, Any, Optional
from dataclasses import dataclass
from fastapi import HTTPException

from .exceptions import (
    ServiceConnectionError,
    ServiceResponseError,
    ServiceConfigurationError,
    ServiceDeserializationError
)

logger = logging.getLogger(__name__)

def extract_bearer_token(authorization: str | None) -> str:
    """Extract the token from a Bearer authorization header.
    
    Args:
        authorization: The authorization header value

    Returns:
        The extracted token

    Raises:
        HTTPException: If the authorization header is missing or invalid
    """
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    raise HTTPException(401, "Missing or invalid Bearer token")

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

@dataclass
class ServiceCaller:
    """Handles API calls and response processing for services."""
    service_name: str
    base_url: str
    ep_api_token: Optional[str] = None

    def _make_api_call(self, payload: Dict[str, Any]) -> requests.Response:
        """Makes the API request to the gateway and returns the response object."""
        url = f"{self.base_url.rstrip('/')}/service/"
        response = None # Initialize response to None
        try:
            response = requests.post(url, json=payload)
            response.raise_for_status() # Raises HTTPError for 4xx/5xx
            return response
        except requests.exceptions.HTTPError as e:
            # Raise ServiceResponseError for bad status codes
            error_message = f"Error calling service '{self.service_name}' at {url}. Server returned status {e.response.status_code}."
            try:
                error_message += f" Response: {e.response.text}"
            except Exception:
                error_message += " Response content could not be read."
            print(error_message) # Keep print for logging, but raise specific error
            raise ServiceResponseError(error_message) from e
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            # Raise ServiceConnectionError for connection issues
            error_message = f"Error connecting to service '{self.service_name}' at {url}: {e}"
            print(error_message)
            raise ServiceConnectionError(error_message) from e
        except requests.exceptions.RequestException as e:
            # Catch other potential request errors (e.g., invalid URL, too many redirects)
            error_message = f"Error during request for service '{self.service_name}' at {url}: {e}"
            if response is not None:
                error_message += f"\nResponse status (potentially before error): {response.status_code}"
                try:
                    error_message += f"\nResponse content: {response.text}"
                except Exception:
                    error_message += "\nResponse content could not be read."
            print(error_message)
            # Use ServiceConnectionError as a general category for request issues
            raise ServiceConnectionError(error_message) from e

    def call_service(self, prepared_params: Dict[str, Any], deserialize_response: callable) -> Any:
        """
        Makes a service call with progress reporting and response handling.

        Args:
            prepared_params: The prepared parameters for the service call
            deserialize_response: Function to deserialize the response

        Returns:
            The deserialized response from the service

        Raises:
            ServiceConfigurationError: If base_url is not set
            ServiceConnectionError: If the API call fails due to connection issues
            ServiceResponseError: If the API call returns an error status or invalid JSON
            ServiceDeserializationError: If the response cannot be deserialized correctly
        """
        if not self.base_url:
            raise ServiceConfigurationError(f"Service '{self.service_name}' cannot be called. Configuration missing (base_url).")

        # Construct the payload
        payload = {
            "service": self.service_name,
            "params": prepared_params
        }
        if self.ep_api_token:
            payload["ep_api_token"] = self.ep_api_token

        # Display a spinner with elapsed-time feedback while the request is in flight
        logger.info("Calling service '%s' via gateway...", self.service_name)
        spinner = ProgressSpinner(message=f"Calling service '{self.service_name}' via gateway")
        
        spinner.start()
        try:
            response = self._make_api_call(payload)
            return deserialize_response(response)
        finally:
            spinner.stop()

        # Note: Cost logging is handled by the ServiceDefinition class since it has access to the cost configuration 
"""
Exceptions specific to the key_management module.

This module defines custom exception classes for all key management-related errors
in the EDSL framework, ensuring consistent error handling and user feedback.
"""

from ..base import BaseException


class KeyManagementError(BaseException):
    """
    Base exception class for all key management-related errors.

    This is the parent class for all exceptions related to API key management,
    including key lookup, validation, and configuration.

    Examples:
        ```python
        # Usually not raised directly, but through subclasses
        # For example, when attempting to use an invalid key
        key_lookup.add_key(service="invalid_service", key="api_key")  # Would raise KeyManagementServiceError
        ```
    """

    relevant_doc = "https://docs.expectedparrot.com/en/latest/api_keys.html"


class KeyManagementValueError(KeyManagementError):
    """
    Exception raised when invalid values are provided to key management operations.

    This exception occurs when:
    - Invalid fetch orders or configuration parameters are provided
    - API key format is invalid
    - Service names don't match expected values

    Examples:
        ```python
        # Invalid fetch order
        key_lookup_builder.set_fetch_order("invalid_order")  # Raises KeyManagementValueError
        ```
    """

    relevant_doc = "https://docs.expectedparrot.com/en/latest/api_keys.html"


class KeyManagementDuplicateError(KeyManagementError):
    """
    Exception raised when duplicate keys or services are encountered.

    This exception occurs when:
    - Attempting to add a duplicate service ID
    - Adding a key that already exists for a service
    - Registering multiple handlers for the same service

    Examples:
        ```python
        # Adding a duplicate service
        builder.register_env_var(service_id="openai", env_var="OPENAI_API_KEY")
        builder.register_env_var(service_id="openai", env_var="ANOTHER_KEY")  # Raises KeyManagementDuplicateError
        ```
    """

    relevant_doc = "https://docs.expectedparrot.com/en/latest/api_keys.html"


class KeyManagementMissingKeyError(KeyManagementError):
    """
    Exception raised when a required API key is missing.

    This exception occurs when:
    - Attempting to use a service (like OpenAI) without setting the required API key
    - The API key environment variable is not set
    - The API key has not been registered through the key management system

    Examples:
        ```python
        # Using a vibe method without setting OPENAI_API_KEY
        ScenarioList.from_vibes("Types of fruit")  # Raises KeyManagementMissingKeyError
        ```
    """

    relevant_doc = "https://docs.expectedparrot.com/en/latest/api_keys.html"
    doc_page = "api_keys"

    def __init__(
        self,
        service: str = "OpenAI",
        env_var: str = "OPENAI_API_KEY",
        message: str = None,
        **kwargs,
    ):
        if message is None:
            message = (
                f"The {service} API key is required but not found.\n\n"
                f"To use this feature, you need to set your {service} API key. "
                f"You can do this by:\n"
                f"1. Setting the {env_var} environment variable\n"
                f"2. Adding it to a .env file in your project root\n"
                f"3. Passing it directly when creating the client\n\n"
                f"For more information on managing API keys, see the documentation link below."
            )
        super().__init__(message, **kwargs)

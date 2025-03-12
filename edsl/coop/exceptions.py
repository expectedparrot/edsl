"""
Exceptions specific to the Expected Parrot cloud service integration.

This module defines exception classes for various error conditions that can
occur when interacting with Expected Parrot's cloud services through the
Coop module. These exceptions help with specific error handling and reporting.
"""

from ..base import BaseException


class CoopErrors(BaseException):
    """
    Base class for all Coop-related exceptions.
    
    This is the parent class for all exceptions raised by the Coop module.
    It inherits from EDSL's BaseException to maintain consistency with
    the library's exception hierarchy.
    
    When catching errors from Coop operations, you can catch this exception
    to handle all Coop-related errors in a single exception handler.
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/using_coop.html"


class CoopInvalidURLError(CoopErrors):
    """
    Exception raised when an invalid URL format is provided.
    
    This exception is raised when a URL provided to the Coop client
    does not match the expected format for object or resource URLs.
    
    To fix this error:
    1. Ensure the URL follows the correct pattern:
       - https://expectedparrot.com/content/{uuid}
       - https://expectedparrot.com/content/{username}/{alias}
    2. Check for typos in the domain name or path structure
    3. Verify that you're using a complete URL rather than just a UUID or path
    
    Example:
        >>> coop = Coop()
        >>> coop.get("https://wrongdomain.com/content/123")  # Raises CoopInvalidURLError
        >>> coop.get("https://expectedparrot.com/wrong-path/123")  # Raises CoopInvalidURLError
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/using_coop.html#accessing-content"


class CoopNoUUIDError(CoopErrors):
    """
    Exception raised when a required UUID or identifier is missing.
    
    This exception is raised when an operation requires a UUID or other
    identifier, but none was provided.
    
    To fix this error:
    1. Ensure you're providing either a valid UUID or a complete URL to the operation
    2. If using an alias instead of a UUID, make sure the alias exists and is formatted correctly
    
    Example:
        >>> coop = Coop()
        >>> coop.get()  # Raises CoopNoUUIDError - missing required UUID or URL
        >>> coop.get("")  # Raises CoopNoUUIDError - empty string is not a valid UUID
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/using_coop.html#accessing-content"


class CoopServerResponseError(CoopErrors):
    """
    Exception raised when the server returns an error response.
    
    This exception is raised when the Expected Parrot API returns an error
    response, such as authentication failures, rate limits, or server errors.
    The exception message typically includes the error details from the server.
    
    To fix this error:
    1. Check the exception message for specific error details from the server
    2. For authentication errors (401), verify your API key is correct and not expired
    3. For rate limit errors (429), reduce the frequency of your requests
    4. For server errors (500+), the issue may be temporary - wait and try again
    5. Check your network connection if you're getting connection timeout errors
    
    Example:
        >>> coop = Coop(api_key="invalid-key")
        >>> coop.get("valid-uuid")  # Raises CoopServerResponseError with 401 Unauthorized
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/api_keys.html"

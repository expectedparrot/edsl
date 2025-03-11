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
    """
    pass


class CoopInvalidURLError(CoopErrors):
    """
    Exception raised when an invalid URL format is provided.
    
    This exception is raised when a URL provided to the Coop client
    does not match the expected format for object or resource URLs.
    
    Example:
        When a URL doesn't follow the pattern:
        - https://expectedparrot.com/content/{uuid}
        - https://expectedparrot.com/content/{username}/{alias}
    """
    pass


class CoopNoUUIDError(CoopErrors):
    """
    Exception raised when a required UUID or identifier is missing.
    
    This exception is raised when an operation requires a UUID or other
    identifier, but none was provided.
    
    Example:
        When calling get() without providing a UUID or URL
    """
    pass


class CoopServerResponseError(CoopErrors):
    """
    Exception raised when the server returns an error response.
    
    This exception is raised when the Expected Parrot API returns an error
    response, such as authentication failures, rate limits, or server errors.
    The exception message typically includes the error details from the server.
    
    Example:
        When the server returns a 401 Unauthorized response due to an invalid API key
    """
    pass

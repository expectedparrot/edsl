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
        ```python
        coop = Coop()
        coop.get("https://wrongdomain.com/content/123")  # Raises CoopInvalidURLError
        coop.get("https://expectedparrot.com/wrong-path/123")  # Raises CoopInvalidURLError
        ```
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
        ```python
        coop = Coop()
        coop.get()  # Raises CoopNoUUIDError - missing required UUID or URL
        coop.get("")  # Raises CoopNoUUIDError - empty string is not a valid UUID
        ```
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
        ```python
        coop = Coop(api_key="invalid-key")
        coop.get("valid-uuid")  # Raises CoopServerResponseError with 401 Unauthorized
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/api_keys.html"


class CoopInvalidMethodError(CoopErrors):
    """
    Exception raised when an invalid method is requested.
    
    This exception is raised when attempting to use an HTTP method that is not
    supported by the Coop API client or by a specific endpoint.
    
    To fix this error:
    1. Check that you're using a valid HTTP method (GET, POST, PUT, DELETE, PATCH)
    2. Verify that the endpoint you're accessing supports the method you're using
    3. Consider using a higher-level method in the Coop class rather than direct HTTP methods
    
    Example:
        ```python
        coop = Coop()
        coop._request("INVALID_METHOD", "/endpoint")  # Raises CoopInvalidMethodError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/using_coop.html"


class CoopResponseError(CoopErrors):
    """
    Exception raised when there's an issue with the server response.
    
    This exception is raised when the server response cannot be processed or
    is missing expected data, even though the HTTP status code might be successful.
    
    To fix this error:
    1. Check the exception message for details about what data was missing
    2. Verify that your request contains all required parameters
    3. Ensure you're using the correct endpoint for your intended operation
    
    Example:
        ```python
        coop = Coop()
        # Assuming an endpoint that returns incomplete data
        coop.get("some-resource")  # Might raise CoopResponseError if response is malformed
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/using_coop.html"


class CoopObjectTypeError(CoopErrors):
    """
    Exception raised when an object has an unexpected type.
    
    This exception is raised when an object retrieved from the server has a type
    that doesn't match what was expected, particularly when using typed methods.
    
    To fix this error:
    1. Make sure you're using the correct method for the object type you want
    2. Verify that the UUID or URL points to the expected object type
    3. Use the generic get() method if you're uncertain about the object type
    
    Example:
        ```python
        coop = Coop()
        # Trying to get a Survey object but the UUID points to a Job
        coop.get_survey("job-uuid")  # Raises CoopObjectTypeError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/using_coop.html#accessing-content"


class CoopPatchError(CoopErrors):
    """
    Exception raised when a patch operation cannot be performed.
    
    This exception is raised when attempting to update an object but not
    providing any fields to update, or if the patch operation fails.
    
    To fix this error:
    1. Ensure you're providing at least one field to update
    2. Verify that you have permission to update the object
    3. Check that the object still exists and hasn't been deleted
    
    Example:
        ```python
        coop = Coop()
        coop.patch("object-uuid")  # Raises CoopPatchError if no update fields provided
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/using_coop.html#updating-content"


class CoopValueError(CoopErrors):
    """
    Exception raised when invalid parameters are provided to a Coop operation.
    
    This exception is raised when required parameters are missing or when
    parameters have invalid values.
    
    To fix this error:
    1. Check that all required parameters are provided
    2. Verify that parameter values meet the expected format or constraints
    3. Consult the API documentation for the correct parameter usage
    
    Example:
        ```python
        coop = Coop()
        coop.get_job_results()  # Raises CoopValueError if job_uuid is not provided
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/using_coop.html"


class CoopTypeError(CoopErrors):
    """
    Exception raised when a parameter has an incorrect type.
    
    This exception is raised when a parameter provided to a Coop method
    has a type that doesn't match what's expected.
    
    To fix this error:
    1. Check the expected types of method parameters
    2. Convert parameters to the correct type before passing them
    3. Ensure you're using EDSL objects where required
    
    Example:
        ```python
        coop = Coop()
        coop.create("not_an_edsl_object")  # Raises CoopTypeError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/using_coop.html"


class CoopTimeoutError(CoopErrors):
    """
    Exception raised when a Coop operation times out.
    
    This exception is raised when an operation takes longer than the
    specified timeout period to complete.
    
    To fix this error:
    1. Increase the timeout value for long-running operations
    2. Check your network connection if timeouts occur frequently
    3. For login operations, try again or use API key authentication instead
    
    Example:
        ```python
        coop = Coop()
        coop.login(timeout=1)  # Raises CoopTimeoutError if login takes longer than 1 second
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/using_coop.html"

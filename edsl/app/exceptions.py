"""
App-specific exception classes.

This module defines custom exceptions for the app module, extending the BaseException
class to provide consistent error handling throughout the EDSL framework.
"""

from ..base.base_exception import BaseException


class FailedToDeleteAppError(BaseException):
    """
    Exception raised when a failed to delete an app.
    """

    relevant_doc = "https://docs.expectedparrot.com/en/latest/apps.html"
    
    def __init__(self, message="Failed to delete app", **kwargs):
        super().__init__(message, **kwargs)


class AppError(BaseException):
    """
    Base exception for app-related errors.

    This exception is the parent class for all app-specific exceptions in EDSL.
    It provides consistent error handling and documentation links for app-related issues.
    """

    relevant_doc = "https://docs.expectedparrot.com/en/latest/apps.html"

    def __init__(self, message="App error occurred", **kwargs):
        super().__init__(message, **kwargs)


class AppValueError(AppError):
    """
    Exception raised for invalid values in app operations.

    This exception is raised when an operation in the app module encounters an
    inappropriate value that prevents it from being completed successfully.

    Examples:
        - Invalid parameter values
        - Missing required parameters
        - Parameter values outside acceptable ranges
    """

    relevant_doc = "https://docs.expectedparrot.com/en/latest/apps.html"

    def __init__(self, message="Invalid value provided for app operation", **kwargs):
        super().__init__(message, **kwargs)


class AppTypeError(AppError):
    """
    Exception raised for type-related errors in app operations.

    This exception is raised when an operation in the app module encounters
    an inappropriate type that prevents it from being completed successfully.

    Examples:
        - Function arguments of incorrect type
        - Type conversion failures
        - Incompatible types in operations
    """

    relevant_doc = "https://docs.expectedparrot.com/en/latest/apps.html"

    def __init__(self, message="Invalid type provided for app operation", **kwargs):
        super().__init__(message, **kwargs)


class ApplicationNameError(AppValueError):
    """
    Exception raised for invalid application names.

    This exception is raised when an application name does not meet the required
    format constraints:
        - The pretty name must not exceed the maximum character length
        - The alias must be a valid Python identifier
        - Required fields must be provided

    Examples:
        - Application name exceeds maximum length
        - Alias contains invalid characters
        - Missing required name or alias
    """

    relevant_doc = "https://docs.expectedparrot.com/en/latest/apps.html"

    def __init__(self, message="Invalid application name", **kwargs):
        super().__init__(message, **kwargs)


class DescriptionError(AppValueError):
    """
    Exception raised for invalid application descriptions.

    This exception is raised when an application description does not meet the
    required format constraints:
        - Short description must be a single sentence ending with a period
        - Long description should be a paragraph
        - Required fields must be provided

    Examples:
        - Short description missing period
        - Short description contains multiple sentences
        - Missing required description fields
    """

    relevant_doc = "https://docs.expectedparrot.com/en/latest/apps.html"

    def __init__(self, message="Invalid application description", **kwargs):
        super().__init__(message, **kwargs)


class DuplicateAppException(AppError):
    """
    Exception raised when attempting to deploy an app with a duplicate qualified name.

    This is raised by the client when the server responds with HTTP 409 Conflict
    due to an existing app with the same "owner/alias" combination.
    """

    relevant_doc = "https://docs.expectedparrot.com/en/latest/apps.html"

    def __init__(self, message: str = "Duplicate app: owner/alias already exists", **kwargs):
        super().__init__(message, **kwargs)

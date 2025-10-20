"""
Macro-specific exception classes.

This module defines custom exceptions for the macro module, extending the BaseException
class to provide consistent error handling throughout the EDSL framework.
"""

from ..base.base_exception import BaseException


class ClientModeError(BaseException):
    """
    Exception raised when a method is called in client mode.
    """

    relevant_doc = "https://docs.expectedparrot.com/en/latest/macros.html"

    def __init__(self, message="Method called in client mode", **kwargs):
        super().__init__(message, **kwargs)


class FailedToDeleteMacroError(BaseException):
    """
    Exception raised when a failed to delete a macro.
    """

    relevant_doc = "https://docs.expectedparrot.com/en/latest/macros.html"

    def __init__(self, message="Failed to delete macro", **kwargs):
        super().__init__(message, **kwargs)


class MacroError(BaseException):
    """
    Base exception for macro-related errors.

    This exception is the parent class for all macro-specific exceptions in EDSL.
    It provides consistent error handling and documentation links for macro-related issues.
    """

    relevant_doc = "https://docs.expectedparrot.com/en/latest/macros.html"

    def __init__(self, message="Macro error occurred", **kwargs):
        super().__init__(message, **kwargs)


class MacroValueError(MacroError):
    """
    Exception raised for invalid values in macro operations.

    This exception is raised when an operation in the macro module encounters an
    inappropriate value that prevents it from being completed successfully.

    Examples:
        - Invalid parameter values
        - Missing required parameters
        - Parameter values outside acceptable ranges
    """

    relevant_doc = "https://docs.expectedparrot.com/en/latest/macros.html"

    def __init__(self, message="Invalid value provided for macro operation", **kwargs):
        super().__init__(message, **kwargs)


class MacroTypeError(MacroError):
    """
    Exception raised for type-related errors in macro operations.

    This exception is raised when an operation in the macro module encounters
    an inappropriate type that prevents it from being completed successfully.

    Examples:
        - Function arguments of incorrect type
        - Type conversion failures
        - Incompatible types in operations
    """

    relevant_doc = "https://docs.expectedparrot.com/en/latest/macros.html"

    def __init__(self, message="Invalid type provided for macro operation", **kwargs):
        super().__init__(message, **kwargs)


class MacroNameError(MacroValueError):
    """
    Exception raised for invalid macro names.

    This exception is raised when a macro name does not meet the required
    format constraints:
        - The pretty name must not exceed the maximum character length
        - The alias must be a valid Python identifier
        - Required fields must be provided

    Examples:
        - Macro name exceeds maximum length
        - Alias contains invalid characters
        - Missing required name or alias
    """

    relevant_doc = "https://docs.expectedparrot.com/en/latest/macros.html"

    def __init__(self, message="Invalid macro name", **kwargs):
        super().__init__(message, **kwargs)


class DescriptionError(MacroValueError):
    """
    Exception raised for invalid macro descriptions.

    This exception is raised when a macro description does not meet the
    required format constraints:
        - Short description must be a single sentence ending with a period
        - Long description should be a paragraph
        - Required fields must be provided

    Examples:
        - Short description missing period
        - Short description contains multiple sentences
        - Missing required description fields
    """

    relevant_doc = "https://docs.expectedparrot.com/en/latest/macros.html"

    def __init__(self, message="Invalid macro description", **kwargs):
        super().__init__(message, **kwargs)


class DuplicateMacroException(MacroError):
    """
    Exception raised when attempting to deploy a macro with a duplicate qualified name.

    This is raised by the client when the server responds with HTTP 409 Conflict
    due to an existing macro with the same "owner/alias" combination.
    """

    relevant_doc = "https://docs.expectedparrot.com/en/latest/macros.html"

    def __init__(
        self, message: str = "Duplicate macro: owner/alias already exists", **kwargs
    ):
        super().__init__(message, **kwargs)

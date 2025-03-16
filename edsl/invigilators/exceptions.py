"""
Exceptions specific to the invigilators module.

This module defines custom exception classes for all invigilator-related errors
in the EDSL framework, ensuring consistent error handling and user feedback.
"""

from ..base import BaseException


class InvigilatorError(BaseException):
    """
    Base exception class for all invigilator-related errors.
    
    This is the parent class for all exceptions related to invigilator creation,
    execution, and management in the EDSL framework.
    
    Examples:
        ```python
        # Usually not raised directly, but through subclasses
        # For example, when attempting to use an unimplemented feature
        invigilator.encode_image(image_path)  # Would raise InvigilatorNotImplementedError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/agents.html#invigilators"


class InvigilatorTypeError(InvigilatorError):
    """
    Exception raised when there's a type mismatch in invigilator operations.
    
    This exception occurs when:
    - Invalid input types are provided to invigilator methods
    - Template variables have incompatible types
    - Return value types don't match expected types
    
    Examples:
        ```python
        # Providing an invalid type to an invigilator method
        invigilator.process_options(123)  # Raises InvigilatorTypeError if expected a dict
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/agents.html#invigilators"


class InvigilatorValueError(InvigilatorError):
    """
    Exception raised when invalid values are provided to invigilator operations.
    
    This exception occurs when:
    - Template variables are missing or invalid
    - Option values don't match expected patterns
    - Configuration values are outside allowed ranges
    
    Examples:
        ```python
        # Template with invalid variables
        invigilator.process_template("Hello {{ missing }}")  # Raises InvigilatorValueError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/agents.html#invigilators"


class InvigilatorNotImplementedError(InvigilatorError):
    """
    Exception raised when attempting to use an unimplemented feature.
    
    This exception occurs when:
    - Calling methods that are not implemented in a specific invigilator
    - Using features only available in certain invigilator types
    - Using planned functionality that is not yet available
    
    Examples:
        ```python
        # Attempting to use image encoding when not implemented
        invigilator.encode_image(image_path)  # Raises InvigilatorNotImplementedError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/agents.html#invigilators"
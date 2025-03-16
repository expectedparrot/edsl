"""
Base-specific exception classes.

This module defines custom exceptions for the base module, extending the BaseException
class to provide consistent error handling throughout the EDSL framework.
"""

from .base_exception import BaseException

class BaseValueError(BaseException):
    """
    Exception raised for invalid values in base module operations.
    
    This exception is raised when an operation in the base module encounters an
    inappropriate value that prevents it from being completed successfully. It 
    replaces standard ValueError with domain-specific error handling.
    
    Examples:
        - Missing required parameters
        - Parameter values outside acceptable ranges
        - Incompatible parameter combinations
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/base.html"
    
    def __init__(self, message="Invalid value provided", **kwargs):
        super().__init__(message, **kwargs)

class BaseNotImplementedError(BaseException):
    """
    Exception raised when a method that should be implemented is not.
    
    This exception is raised when calling an abstract or unimplemented method 
    in the base module. It should be used for methods that are expected to be
    overridden by subclasses but have not been implemented yet.
    
    Examples:
        - Abstract methods called directly
        - Interface methods not yet implemented
        - Placeholder methods requiring implementation
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/base.html"
    
    def __init__(self, message="This method is not implemented yet", **kwargs):
        super().__init__(message, **kwargs)

class BaseKeyError(BaseException):
    """
    Exception raised for missing keys in base module operations.
    
    This exception is raised when a required key is missing from a dictionary
    or similar data structure in the base module.
    
    Examples:
        - Accessing a non-existent key in a configuration dictionary
        - Missing required fields in serialized data
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/base.html"
    
    def __init__(self, message="Required key not found", **kwargs):
        super().__init__(message, **kwargs)

class BaseFileError(BaseException):
    """
    Exception raised for file-related errors in base module operations.
    
    This exception is raised when file operations in the base module encounter
    issues such as missing files, permission problems, or format errors.
    
    Examples:
        - File not found
        - File format incompatible with the operation
        - Permission denied when accessing a file
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/base.html"
    
    def __init__(self, message="Error in file operation", **kwargs):
        super().__init__(message, **kwargs)

class BaseTypeError(BaseException):
    """
    Exception raised for type-related errors in base module operations.
    
    This exception is raised when an operation in the base module encounters
    an inappropriate type that prevents it from being completed successfully.
    
    Examples:
        - Function arguments of incorrect type
        - Type conversion failures
        - Incompatible types in operations
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/base.html"
    
    def __init__(self, message="Invalid type provided", **kwargs):
        super().__init__(message, **kwargs)
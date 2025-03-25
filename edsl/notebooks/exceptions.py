"""
Custom exceptions for the notebooks module.
"""

from ..base import BaseException


class NotebookError(BaseException):
    """
    Base exception class for all notebook-related errors.
    
    This is the parent class for all exceptions related to notebook
    operations, including creation, validation, and conversion.
    """
    relevant_doc = "https://docs.expectedparrot.com/"


class NotebookValueError(NotebookError):
    """
    Exception raised when an invalid value is provided to a notebook method.
    
    This exception occurs when attempting to create or modify a notebook
    with invalid values, such as:
    - Invalid data format
    - Incompatible notebook contents
    
    Examples:
        ```python
        # Attempting to create a notebook with invalid data
        notebook = Notebook(data=invalid_data)  # Raises NotebookValueError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/"
    

class NotebookFormatError(NotebookError):
    """
    Exception raised when a notebook's format is invalid.
    
    This exception occurs when the notebook structure does not conform
    to the expected Jupyter Notebook format.
    
    Examples:
        ```python
        # Attempting to load a notebook with invalid format
        notebook = Notebook.from_dict(invalid_dict)  # Raises NotebookFormatError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/"


class NotebookConversionError(NotebookError):
    """
    Exception raised when a notebook conversion fails.
    
    This exception occurs when attempting to convert a notebook to another
    format (like LaTeX) and the conversion process fails.
    
    Examples:
        ```python
        # Attempting to convert a notebook to LaTeX with invalid options
        notebook.to_latex(invalid_options)  # Raises NotebookConversionError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/"


class NotebookEnvironmentError(NotebookError):
    """
    Exception raised when the notebook environment is not supportable.
    
    This exception occurs when attempting to create a notebook in an 
    environment that doesn't provide required context, such as when
    trying to create a notebook from within itself outside of VS Code.
    
    Examples:
        ```python
        # Attempting to create a notebook from within itself in an unsupported IDE
        notebook = Notebook()  # Raises NotebookEnvironmentError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/"
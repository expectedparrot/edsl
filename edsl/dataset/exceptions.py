"""
Exceptions module for dataset-related operations.

This module defines custom exception classes for all dataset-related error conditions
in the EDSL framework, ensuring consistent error handling for data manipulation,
transformation, and analysis operations.
"""

from ..base import BaseException


class DatasetError(BaseException):
    """
    Base exception class for all dataset-related errors.
    
    This is the parent class for exceptions related to Dataset operations
    in the EDSL framework, including data creation, manipulation, validation,
    and serialization.
    
    Examples:
        ```python
        # Usually not raised directly, but through subclasses:
        dataset = Dataset([])
        dataset["missing_key"]  # Would raise DatasetKeyError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/dataset.html"


class DatasetKeyError(DatasetError):
    """
    Exception raised when a key is not found in a dataset.
    
    This exception occurs when attempting to access a field or column
    that doesn't exist in the dataset.
    
    Examples:
        ```python
        dataset = Dataset([{"a": 1}])
        dataset["b"]  # Raises DatasetKeyError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/dataset.html"


class DatasetValueError(DatasetError):
    """
    Exception raised when there's an issue with dataset values.
    
    This exception occurs when dataset values are invalid, incompatible
    with an operation, or otherwise problematic.
    
    Examples:
        ```python
        dataset = Dataset([{"a": 1}, {"b": 2}])
        dataset.select(["c"])  # Raises DatasetValueError for missing field
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/dataset.html"


class DatasetTypeError(DatasetError):
    """
    Exception raised when there's a type mismatch in dataset operations.
    
    This exception occurs when trying to perform operations with
    incompatible data types.
    
    Examples:
        ```python
        dataset = Dataset([{"a": 1}])
        dataset + "not a dataset"  # Raises DatasetTypeError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/dataset.html"


class DatasetExportError(DatasetError):
    """
    Exception raised when exporting a dataset to a different format fails.
    
    This exception occurs when trying to export a dataset to a file format
    (like CSV, SQLite, etc.) and the operation fails.
    
    Examples:
        ```python
        dataset = Dataset([{"a": complex(1, 2)}])
        dataset.to_csv("file.csv")  # Raises DatasetExportError (complex not serializable)
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/dataset.html"


class DatasetImportError(DatasetError):
    """
    Exception raised when importing data from an external source fails.
    
    This exception occurs when trying to import data from an external source or format
    (like CSV, JSON, etc.) and the operation fails, often due to missing dependencies
    or format issues.
    
    Examples:
        ```python
        # Trying to export to DOCX without python-docx package
        dataset.to_docx("file.docx")  # Raises DatasetImportError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/dataset.html"


class DatasetRuntimeError(DatasetError):
    """
    Exception raised when an operation fails during runtime.
    
    This exception is used for runtime errors in dataset operations,
    typically for operations that depend on external systems or libraries
    like R integration.
    
    Examples:
        ```python
        # Plotting with ggplot when R is not installed
        dataset.ggplot()  # Raises DatasetRuntimeError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/dataset.html"
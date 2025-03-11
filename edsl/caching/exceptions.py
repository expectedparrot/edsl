"""
Custom exceptions for the data module in the EDSL framework.

This module defines exceptions that are raised during cache operations,
such as when entries cannot be stored, retrieved, or synchronized.
"""

from ..base import BaseException


class CacheError(BaseException):
    """
    Exception raised for errors related to cache operations.
    
    This exception is raised when cache operations fail, such as when:
    - A cache key cannot be generated
    - A cache entry cannot be stored or retrieved
    - A cache synchronization operation fails
    - Cache migration encounters an error
    
    Attributes:
        message (str): Explanation of the error
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/data.html#cache"

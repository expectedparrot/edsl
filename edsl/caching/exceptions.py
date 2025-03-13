"""
Custom exceptions for the caching module in the EDSL framework.

This module defines exceptions that are raised during cache operations,
such as when entries cannot be stored, retrieved, or synchronized.
"""

from ..base import BaseException


class CacheError(BaseException):
    """
    Exception raised for errors related to cache operations.
    
    This exception is raised when cache operations fail, such as when:
    - A cache key cannot be generated due to invalid or non-serializable inputs
    - A cache entry cannot be stored or retrieved due to database access issues
    - A cache synchronization operation fails when syncing with remote cache
    - Cache migration encounters an error when upgrading between versions
    
    To resolve this error:
    1. Check that your inputs to cached functions are serializable
    2. Ensure you have proper file system permissions for the SQLite cache file
    3. For remote cache issues, verify your network connection and API credentials
    4. For migration issues, you may need to clear the cache by calling cache.clear()
    
    Examples:
        ```python
        # Cache key generation failure
        @cache
        def my_function(non_serializable_object):  # Raises CacheError
            return result
        
        # Storage failure
        cache.set("key", "value")  # May raise CacheError if DB is locked
        ```
    
    Attributes:
        message (str): Detailed explanation of the error
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/remote_caching.html"

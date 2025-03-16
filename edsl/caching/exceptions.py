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


class CacheFileNotFoundError(CacheError):
    """
    Exception raised when a cache file cannot be found.
    
    This exception is raised when attempting to load or access a cache file
    that does not exist on the filesystem.
    
    To resolve this error:
    1. Check that the file path is correct
    2. Verify that the file exists and has proper permissions
    3. If you're loading a serialized cache, make sure it was previously saved
    
    Examples:
        ```python
        # Attempting to load a non-existent cache file
        cache.load_from_file("non_existent_file.json")  # Raises CacheFileNotFoundError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/remote_caching.html"


class CacheValueError(CacheError):
    """
    Exception raised when an invalid value is provided to a cache operation.
    
    This exception is raised when:
    - An incorrect type is provided for a cache entry
    - A value cannot be serialized for storage
    - A validation check fails during cache operations
    
    To resolve this error:
    1. Ensure the value has the expected type and structure
    2. Verify that values being stored are serializable
    3. Check for any special requirements in the cache implementation
    
    Examples:
        ```python
        # Attempting to store an invalid value type
        cache_dict["key"] = non_cache_entry_object  # Raises CacheValueError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/remote_caching.html"


class CacheKeyError(CacheError):
    """
    Exception raised when a key cannot be found in the cache.
    
    This exception is raised when attempting to access a cache entry that
    does not exist in the cache.
    
    To resolve this error:
    1. Check that the key exists before accessing it
    2. Use cache.get() with a default value to handle missing keys gracefully
    3. Consider initializing the key-value pair before accessing
    
    Examples:
        ```python
        # Attempting to access a non-existent key
        value = cache["non_existent_key"]  # Raises CacheKeyError
        
        # Safer alternative
        value = cache.get("non_existent_key", default=None)  # Returns None instead of raising
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/remote_caching.html"


class CacheNotImplementedError(CacheError):
    """
    Exception raised when a cache method is not implemented.
    
    This exception is raised when attempting to use a method that is
    defined in the interface but not implemented in the concrete class.
    
    To resolve this error:
    1. Check if the operation is supported by the specific cache implementation
    2. Consider using an alternative approach that is supported
    3. If you're implementing a custom cache, implement the required method
    
    Examples:
        ```python
        # Attempting to use an unimplemented method
        cache.some_unimplemented_method()  # Raises CacheNotImplementedError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/en/latest/remote_caching.html"

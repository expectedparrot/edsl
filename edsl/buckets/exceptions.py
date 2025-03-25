"""
Exceptions module for bucket-related operations.

This module defines custom exception classes for all bucket-related error conditions
in the EDSL framework, ensuring consistent error handling for token bucket operations,
rate limiting, and related functionality.
"""

from ..base import BaseException


class BucketError(BaseException):
    """
    Base exception class for all bucket-related errors.
    
    This is the parent class for exceptions related to token bucket operations
    in the EDSL framework, including token management, rate limiting, and related
    functionality.
    
    Examples:
        ```python
        # Usually not raised directly, but through subclasses:
        bucket = TokenBucket(name="test", capacity=100, refill_rate=10)
        bucket.get_tokens(200)  # Would raise TokenLimitError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/"


class TokenLimitError(BucketError):
    """
    Exception raised when a token request exceeds available limits.
    
    This exception occurs when attempting to request more tokens than
    are currently available in the bucket or when exceeding rate limits.
    
    Examples:
        ```python
        bucket = TokenBucket(name="test", capacity=100, refill_rate=10)
        bucket.get_tokens(200)  # Raises TokenLimitError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/"


class TokenBucketClientError(BucketError):
    """
    Exception raised when there's an error communicating with a remote token bucket.
    
    This exception occurs when the client cannot connect to the token bucket service,
    receives an unexpected response, or encounters other client-related issues.
    
    Examples:
        ```python
        client = TokenBucketClient(url="invalid_url")
        client.get_tokens(10)  # May raise TokenBucketClientError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/"


class BucketConfigurationError(BucketError):
    """
    Exception raised when there's an issue with bucket configuration.
    
    This exception occurs when bucket parameters are invalid, such as
    negative capacity, invalid refill rates, or other configuration problems.
    
    Examples:
        ```python
        # Attempting to create a bucket with invalid parameters:
        TokenBucket(name="test", capacity=-100, refill_rate=10)  # Would raise BucketConfigurationError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/"


class BucketNotFoundError(BucketError):
    """
    Exception raised when a requested bucket cannot be found.
    
    This exception occurs when attempting to access a bucket that doesn't exist
    in the system or has been removed.
    
    Examples:
        ```python
        # Attempting to access a non-existent bucket:
        bucket_collection.get_bucket("non_existent_bucket")  # Would raise BucketNotFoundError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/"
    
    
class InvalidBucketParameterError(BucketConfigurationError):
    """
    Exception raised when an invalid parameter is provided for bucket operations.
    
    This exception occurs when providing invalid parameters to bucket methods,
    such as negative token amounts, invalid capacity values, etc.
    
    Examples:
        ```python
        # Attempting to use invalid parameters:
        bucket.add_tokens(-100)  # Would raise InvalidBucketParameterError
        ```
    """
    relevant_doc = "https://docs.expectedparrot.com/"
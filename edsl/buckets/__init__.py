"""
Buckets module for managing rate limits of language model API requests.

This module provides a rate-limiting system for language model API calls,
implementing the token bucket algorithm to manage both requests-per-minute and
tokens-per-minute limits.

Key components:
- TokenBucket: Core rate-limiting class implementing the token bucket algorithm
- ModelBuckets: Manages rate limits for a specific language model, containing
  separate buckets for requests and tokens
- BucketCollection: Manages multiple ModelBuckets instances across different
  language model services
"""

from .exceptions import (
    BucketError,
    TokenLimitError,
    BucketConfigurationError,
)

from .token_bucket import TokenBucket
from .model_buckets import ModelBuckets

# Import BucketCollection last to avoid circular import issues
from .bucket_collection import BucketCollection

__all__ = [
    "BucketCollection",
    "ModelBuckets",
    "TokenBucket",
    "BucketError",
    "TokenLimitError",
    "BucketConfigurationError",
]

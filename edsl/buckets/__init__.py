"""
Buckets module for managing rate limits of language model API requests.

This module provides a robust rate-limiting system for language model API calls,
implementing the token bucket algorithm to manage both requests-per-minute and
tokens-per-minute limits. It supports both local (in-process) and remote
(distributed) rate limiting through a client-server architecture.

Key components:
- TokenBucket: Core rate-limiting class implementing the token bucket algorithm
- ModelBuckets: Manages rate limits for a specific language model, containing
  separate buckets for requests and tokens
- BucketCollection: Manages multiple ModelBuckets instances across different
  language model services

The module also includes a FastAPI server implementation (token_bucket_api) and
client (token_bucket_client) for distributed rate limiting scenarios where
multiple processes or machines need to share rate limits.
"""

from .bucket_collection import BucketCollection
from .model_buckets import ModelBuckets
from .token_bucket import TokenBucket
from .exceptions import (
    BucketError,
    TokenLimitError,
    TokenBucketClientError,
    BucketConfigurationError,
)

__all__ = [
    "BucketCollection", 
    "ModelBuckets", 
    "TokenBucket",
    "BucketError",
    "TokenLimitError",
    "TokenBucketClientError",
    "BucketConfigurationError",
]

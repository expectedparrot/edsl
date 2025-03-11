"""
Caching module for EDSL framework.

This module provides caching functionality for language model responses,
with support for both in-memory and persistent storage through SQLite.
It includes components for managing cache entries, handling cache initialization 
and migration, and synchronizing with remote caches.

Key components:
- Cache: Central class for storing and retrieving language model responses
- CacheEntry: Represents individual cached responses with metadata
- CacheHandler: Manages cache initialization and migration
- SQLiteDict: Dictionary-like interface to SQLite database
"""

from .cache import Cache
from .cache_entry import CacheEntry
from .cache_handler import CacheHandler

__all__ = ["Cache", "CacheEntry", "CacheHandler"]

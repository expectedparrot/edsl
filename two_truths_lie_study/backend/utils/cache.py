"""Simple in-memory cache with TTL support."""

from datetime import datetime, timedelta
from typing import Any, Optional
import logging

logger = logging.getLogger(__name__)


class SimpleCache:
    """In-memory cache with TTL support."""

    def __init__(self, ttl_hours: int = 24):
        """Initialize cache with TTL in hours.

        Args:
            ttl_hours: Time to live in hours (default 24)
        """
        self.ttl_hours = ttl_hours
        self._cache: dict[str, tuple[Any, datetime]] = {}

    def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired.

        Args:
            key: Cache key

        Returns:
            Cached value if found and not expired, None otherwise
        """
        if key not in self._cache:
            return None

        value, timestamp = self._cache[key]
        expiry = timestamp + timedelta(hours=self.ttl_hours)

        if datetime.now() > expiry:
            logger.info(f"Cache expired for key: {key}")
            del self._cache[key]
            return None

        logger.debug(f"Cache hit for key: {key}")
        return value

    def set(self, key: str, value: Any) -> None:
        """Set value in cache with current timestamp.

        Args:
            key: Cache key
            value: Value to cache
        """
        self._cache[key] = (value, datetime.now())
        logger.debug(f"Cache set for key: {key}")

    def clear(self, key: Optional[str] = None) -> None:
        """Clear cache for specific key or all keys.

        Args:
            key: Cache key to clear, or None to clear all
        """
        if key is None:
            self._cache.clear()
            logger.info("Cache cleared (all keys)")
        elif key in self._cache:
            del self._cache[key]
            logger.info(f"Cache cleared for key: {key}")

    def get_timestamp(self, key: str) -> Optional[datetime]:
        """Get timestamp when key was cached.

        Args:
            key: Cache key

        Returns:
            Timestamp when cached, or None if not found
        """
        if key not in self._cache:
            return None
        return self._cache[key][1]

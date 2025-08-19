"""
Global cache for file uploads to external services.

This module provides a thread-safe, singleton cache for managing file uploads
to external services like Google's Generative AI. It prevents duplicate uploads
of the same file and handles concurrent access safely.
"""

import asyncio
import hashlib
import time
from typing import Dict, Any, TYPE_CHECKING
from threading import Lock

if TYPE_CHECKING:
    from .file_store import FileStore


class FileUploadCache:
    """
    Global cache for uploaded files with thread-safe access.

    This singleton class manages a cache of uploaded files to prevent duplicate
    uploads when multiple interviews or async operations need the same file.
    It uses per-file locks to ensure only one upload happens per unique file.

    Attributes:
        _instance: Singleton instance of the cache
        _cache: Dictionary mapping file hashes to upload results
        _locks: Dictionary mapping file hashes to asyncio locks
        _creation_lock: Thread lock for singleton creation
        _stats: Statistics about cache hits and uploads
    """

    _instance = None
    _creation_lock = Lock()

    def __new__(cls):
        """Ensure singleton pattern - only one instance exists."""
        if cls._instance is None:
            with cls._creation_lock:
                # Double-check after acquiring lock
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the cache if not already initialized."""
        if not self._initialized:
            self._cache: Dict[str, Dict[str, Any]] = {}
            self._locks: Dict[str, asyncio.Lock] = {}
            self._stats = {
                "cache_hits": 0,
                "cache_misses": 0,
                "upload_errors": 0,
                "total_upload_time": 0.0,
                "duplicate_prevention_count": 0,
            }
            self._initialized = True

    @classmethod
    def reset(cls):
        """Reset the cache (useful for testing)."""
        with cls._creation_lock:
            if cls._instance:
                cls._instance._cache.clear()
                cls._instance._locks.clear()
                cls._instance._stats = {
                    "cache_hits": 0,
                    "cache_misses": 0,
                    "upload_errors": 0,
                    "total_upload_time": 0.0,
                    "duplicate_prevention_count": 0,
                }

    def _get_file_hash(self, file_store) -> str:
        """
        Generate a unique hash for a file based on its content.

        Args:
            file_store: FileStore object to hash

        Returns:
            Hexadecimal string hash of the file content
        """
        # Use hashlib for more consistent hashing than Python's hash()
        # Include mime_type to differentiate files with same content but different types
        content_to_hash = f"{file_store.base64_string}:{file_store.mime_type}"
        return hashlib.sha256(content_to_hash.encode()).hexdigest()

    async def get_or_upload(
        self, file_store: "FileStore", service: str = "google"
    ) -> Dict[str, Any]:
        """
        Get cached upload info or upload the file if not cached.

        This method ensures that each unique file is only uploaded once,
        even when multiple async operations request it simultaneously.

        Args:
            file_store: FileStore object to upload
            service: External service name (default: "google")

        Returns:
            Dictionary containing the upload information for the service

        Raises:
            Exception: If upload fails after retries
        """
        file_hash = self._get_file_hash(file_store)
        cache_key = f"{file_hash}:{service}"

        # Fast path - check if already in cache
        if cache_key in self._cache:
            self._stats["cache_hits"] += 1
            # Also update the file_store's external_locations
            file_store.external_locations[service] = self._cache[cache_key]
            return self._cache[cache_key]

        # Create lock for this file if it doesn't exist
        if file_hash not in self._locks:
            self._locks[file_hash] = asyncio.Lock()

        # Acquire lock for this specific file
        print(f"Acquiring lock for file: {file_hash}")
        async with self._locks[file_hash]:
            # Double-check after acquiring lock (another task might have uploaded)
            print("inside the lock")
            if cache_key in self._cache:
                print(f"File {file_hash} already uploaded, returning cached result")
                self._stats["duplicate_prevention_count"] += 1
                file_store.external_locations[service] = self._cache[cache_key]
                return self._cache[cache_key]

            # File not in cache, need to upload
            self._stats["cache_misses"] += 1
            start_time = time.time()
            print("service", cache_key, service)
            try:
                if service == "google":
                    # Use async version of upload if available, otherwise run in executor

                    if hasattr(file_store, "async_upload_google"):
                        print(
                            f"Uploading file {file_store.name} to Google service",
                            file_store,
                        )
                        result = await file_store.async_upload_google()
                        print(
                            f"Upload completed in {time.time() - start_time:.2f} seconds"
                        )
                    else:
                        # Run synchronous upload in thread pool to avoid blocking
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, file_store.upload_google)
                        result = file_store.external_locations.get("google")
                else:
                    raise ValueError(f"Unsupported service: {service}")

                # Cache the result
                self._cache[cache_key] = result
                self._stats["total_upload_time"] += time.time() - start_time

                # Ensure file_store has the updated external_locations
                file_store.external_locations[service] = result

                return result

            except Exception as e:
                self._stats["upload_errors"] += 1
                print(f"Error uploading file to {service}: {e}")
                raise

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring and debugging."""
        return {
            **self._stats,
            "cache_size": len(self._cache),
            "unique_files": len(set(k.split(":")[0] for k in self._cache.keys())),
            "hit_rate": self._stats["cache_hits"]
            / max(1, self._stats["cache_hits"] + self._stats["cache_misses"]),
        }

    def clear_cache(self):
        """Clear the cache but keep the locks and stats."""
        self._cache.clear()
        print(f"Cache cleared. Stats: {self.get_stats()}")


# Global instance for easy access
file_upload_cache = FileUploadCache()

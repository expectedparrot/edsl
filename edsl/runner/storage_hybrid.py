"""
Hybrid Storage Implementation

A storage implementation that delegates to different backends based on
operation type:
- Volatile operations (state, counters, sets) → Redis
- Persistent operations (definitions, answers) → SQLAlchemy/PostgreSQL
- Blob operations (FileStore content) → Google Cloud Storage

This allows optimal backend selection for each data type without requiring
an HTTP server intermediary.

Usage:
    from storage_hybrid import HybridStorage

    storage = HybridStorage(
        volatile="redis://localhost:6379",
        persistent="postgresql://user:pass@host/db",
        blob="gs://my-bucket",
    )

    # Use like any other storage implementation
    storage.write_persistent("key", {"data": "value"})
    storage.write_volatile("counter", 0)
    storage.write_blob("file-id", b"binary data")
"""

from typing import Any

from .storage import InMemoryStorage, StorageProtocol
from .storage_redis import RedisStorage, REDIS_AVAILABLE
from .storage_sqlalchemy import SQLAlchemyStorage
from .storage_gcs import GCSBlobStorage, GCS_AVAILABLE


class HybridStorage:
    """
    Hybrid storage that delegates to specialized backends.

    Routes operations to the optimal backend:
    - Redis: Volatile data (fast, in-memory, atomic operations)
    - SQLAlchemy: Persistent data (durable, ACID transactions)
    - GCS: Blob data (scalable object storage)

    If a backend URL is not provided, falls back to in-memory storage
    for that category.

    Thread Safety:
    - Each backend handles its own thread safety
    - Redis and SQLAlchemy backends are thread-safe
    - GCS client is thread-safe
    """

    def __init__(
        self,
        volatile: str | StorageProtocol | None = None,
        persistent: str | StorageProtocol | None = None,
        blob: str | StorageProtocol | None = None,
        prefix: str = "runner",
        all_redis: bool = False,
    ):
        """
        Initialize hybrid storage with backend URLs or instances.

        Args:
            volatile: Redis URL ("redis://...") or StorageProtocol instance.
                     If None, uses InMemoryStorage for volatile ops.
            persistent: SQLAlchemy URL ("sqlite://..." or "postgresql://...")
                       or StorageProtocol instance.
                       If None, uses InMemoryStorage for persistent ops.
            blob: GCS URL ("gs://bucket-name") or blob storage instance.
                 If None, uses InMemoryStorage for blob ops.
            prefix: Key prefix for Redis (default: "runner").
            all_redis: If True, route all persistent operations to Redis instead
                      of SQLAlchemy/PostgreSQL. Useful for performance testing.
        """
        self._all_redis = all_redis

        # Initialize volatile storage (Redis)
        self._volatile = self._create_volatile_storage(volatile, prefix)

        # Initialize persistent storage (SQLAlchemy) - skip if all_redis mode
        if all_redis:
            self._persistent = None  # Don't create PostgreSQL connection
        else:
            self._persistent = self._create_persistent_storage(persistent)

        # Initialize blob storage (GCS)
        self._blob = self._create_blob_storage(blob)

        # Track which backends are in use (for stats/health)
        self._volatile_type = type(self._volatile).__name__
        self._persistent_type = (
            "Redis (all_redis mode)" if all_redis else type(self._persistent).__name__
        )
        self._blob_type = type(self._blob).__name__

    def _create_volatile_storage(
        self, config: str | StorageProtocol | None, prefix: str
    ) -> StorageProtocol:
        """Create volatile storage backend."""
        if config is None:
            return InMemoryStorage()

        if isinstance(config, str):
            if config.startswith("redis://"):
                if not REDIS_AVAILABLE:
                    raise ImportError(
                        "redis package required for Redis storage. "
                        "Install with: pip install redis"
                    )
                return RedisStorage(config, prefix=prefix)
            else:
                raise ValueError(
                    f"Unknown volatile storage URL: {config}. Use redis://..."
                )

        # Assume it's already a StorageProtocol
        return config

    def _create_persistent_storage(
        self, config: str | StorageProtocol | None
    ) -> StorageProtocol:
        """Create persistent storage backend."""
        if config is None:
            return InMemoryStorage()

        if isinstance(config, str):
            if config.startswith("sqlite://") or config.startswith("postgresql://"):
                return SQLAlchemyStorage(config)
            else:
                raise ValueError(
                    f"Unknown persistent storage URL: {config}. "
                    "Use sqlite://... or postgresql://..."
                )

        return config

    def _create_blob_storage(self, config: str | Any | None) -> Any:
        """Create blob storage backend."""
        if config is None:
            return InMemoryStorage()

        if isinstance(config, str):
            # Handle both "gs://bucket-name" and plain "bucket-name" formats
            if config.startswith("gs://"):
                bucket_name = config[5:]  # Strip "gs://"
            else:
                # Plain bucket name without gs:// prefix
                bucket_name = config

            # Remove any trailing path for now
            if "/" in bucket_name:
                bucket_name = bucket_name.split("/")[0]

            if not GCS_AVAILABLE:
                raise ImportError(
                    "google-cloud-storage package required for GCS. "
                    "Install with: pip install google-cloud-storage"
                )
            return GCSBlobStorage(bucket_name=bucket_name)

        return config

    # -------------------------------------------------------------------------
    # Blob Operations (delegated to GCS)
    # -------------------------------------------------------------------------

    def write_blob(
        self, blob_id: str, data: bytes, metadata: dict | None = None
    ) -> None:
        """Write binary blob data to GCS."""
        self._blob.write_blob(blob_id, data, metadata)

    def read_blob(self, blob_id: str) -> bytes | None:
        """Read binary blob data from GCS."""
        return self._blob.read_blob(blob_id)

    def read_blob_metadata(self, blob_id: str) -> dict | None:
        """Read blob metadata from GCS."""
        return self._blob.read_blob_metadata(blob_id)

    def delete_blob(self, blob_id: str) -> None:
        """Delete a blob from GCS."""
        self._blob.delete_blob(blob_id)

    def blob_exists(self, blob_id: str) -> bool:
        """Check if a blob exists in GCS."""
        return self._blob.blob_exists(blob_id)

    # -------------------------------------------------------------------------
    # Persistent Operations (delegated to SQLAlchemy, or Redis if all_redis=True)
    # -------------------------------------------------------------------------

    def write_persistent(self, key: str, value: dict) -> None:
        """Write immutable data to persistent storage."""
        if self._all_redis:
            self._volatile.write_volatile(key, value)
        else:
            self._persistent.write_persistent(key, value)

    def read_persistent(self, key: str) -> dict | None:
        """Read from persistent storage."""
        if self._all_redis:
            return self._volatile.read_volatile(key)
        return self._persistent.read_persistent(key)

    def batch_write_persistent(self, items: dict[str, dict]) -> None:
        """Write multiple items to persistent storage atomically."""
        if self._all_redis:
            self._volatile.batch_write_volatile(items)
        else:
            self._persistent.batch_write_persistent(items)

    def delete_persistent(self, key: str) -> None:
        """Delete a key from persistent storage."""
        if self._all_redis:
            self._volatile.delete_volatile(key)
        else:
            self._persistent.delete_persistent(key)

    def scan_keys_persistent(self, pattern: str) -> list[str]:
        """Scan persistent storage for keys matching pattern."""
        if self._all_redis:
            return self._volatile.scan_keys_volatile(pattern)
        return self._persistent.scan_keys_persistent(pattern)

    # -------------------------------------------------------------------------
    # Volatile Operations (delegated to Redis)
    # -------------------------------------------------------------------------

    def write_volatile(self, key: str, value: str | int | float | dict | list) -> None:
        """Write mutable data to volatile storage."""
        self._volatile.write_volatile(key, value)

    def read_volatile(self, key: str) -> str | int | float | dict | list | None:
        """Read from volatile storage."""
        return self._volatile.read_volatile(key)

    def delete_volatile(self, key: str) -> None:
        """Delete a key from volatile storage."""
        self._volatile.delete_volatile(key)

    def increment_volatile(self, key: str, amount: int = 1) -> int:
        """Atomically increment a counter."""
        return self._volatile.increment_volatile(key, amount)

    def scan_keys_volatile(self, pattern: str) -> list[str]:
        """Scan volatile storage for keys matching pattern."""
        return self._volatile.scan_keys_volatile(pattern)

    def batch_read_volatile(self, keys: list[str]) -> dict:
        """Read multiple keys from volatile storage in a single operation."""
        return self._volatile.batch_read_volatile(keys)

    def batch_write_volatile(self, items: dict) -> None:
        """Write multiple keys to volatile storage in a single operation."""
        self._volatile.batch_write_volatile(items)

    def batch_read_persistent(self, keys: list[str]) -> dict:
        """Read multiple keys from persistent storage in a single operation."""
        if self._all_redis:
            return self._volatile.batch_read_volatile(keys)
        return self._persistent.batch_read_persistent(keys)

    def batch_get_with_set_sizes(
        self, value_keys: list[str], set_keys: list[str]
    ) -> tuple[dict, dict]:
        """
        Read multiple volatile values AND set sizes in a single pipeline call.
        Delegated to Redis storage for efficiency.
        """
        if hasattr(self._volatile, "batch_get_with_set_sizes"):
            return self._volatile.batch_get_with_set_sizes(value_keys, set_keys)
        # Fallback to individual calls if method not available
        values = self.batch_read_volatile(value_keys)
        sizes = {k: self.set_size(k) for k in set_keys}
        return values, sizes

    # -------------------------------------------------------------------------
    # Set Operations (delegated to Redis)
    # -------------------------------------------------------------------------

    def add_to_set(self, key: str, value: str) -> bool:
        """Add value to a set."""
        return self._volatile.add_to_set(key, value)

    def remove_from_set(self, key: str, value: str) -> bool:
        """Remove value from a set."""
        return self._volatile.remove_from_set(key, value)

    def pop_from_set(self, key: str) -> str | None:
        """Atomically remove and return an element from a set."""
        return self._volatile.pop_from_set(key)

    def pop_multiple_from_set(self, key: str, count: int) -> list[str]:
        """Atomically remove and return up to count elements from a set."""
        return self._volatile.pop_multiple_from_set(key, count)

    def add_multiple_to_set(self, key: str, values: list[str]) -> int:
        """Add multiple values to a set in a single operation."""
        return self._volatile.add_multiple_to_set(key, values)

    def get_set_members(self, key: str) -> set[str]:
        """Get all members of a set."""
        return self._volatile.get_set_members(key)

    def set_size(self, key: str) -> int:
        """Get the number of elements in a set."""
        return self._volatile.set_size(key)

    def check_set_membership(self, key: str, values: list[str]) -> list[bool]:
        """Check which values are members of a set (SMISMEMBER)."""
        return self._volatile.check_set_membership(key, values)

    # -------------------------------------------------------------------------
    # Redis Stream Operations (delegated to Redis)
    # -------------------------------------------------------------------------

    def stream_add(
        self,
        stream: str,
        data: dict,
        maxlen: int | None = None,
        approximate: bool = True,
    ) -> str | None:
        """Add a message to a Redis Stream (if volatile backend supports it)."""
        if hasattr(self._volatile, "stream_add"):
            return self._volatile.stream_add(stream, data, maxlen, approximate)
        return None

    def stream_read(
        self,
        stream: str,
        count: int = 10,
        block: int | None = None,
        last_id: str = "0",
    ) -> list:
        """Read messages from a stream."""
        if hasattr(self._volatile, "stream_read"):
            return self._volatile.stream_read(stream, count, block, last_id)
        return []

    def stream_create_group(
        self,
        stream: str,
        group: str,
        start_id: str = "0",
        mkstream: bool = True,
    ) -> bool:
        """Create a consumer group for a stream."""
        if hasattr(self._volatile, "stream_create_group"):
            return self._volatile.stream_create_group(stream, group, start_id, mkstream)
        return False

    def stream_read_group(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
        block: int | None = None,
        pending: bool = False,
    ) -> list:
        """Read messages from a stream using a consumer group."""
        if hasattr(self._volatile, "stream_read_group"):
            return self._volatile.stream_read_group(
                stream, group, consumer, count, block, pending
            )
        return []

    def stream_ack(self, stream: str, group: str, *message_ids: str) -> int:
        """Acknowledge messages as processed."""
        if hasattr(self._volatile, "stream_ack"):
            return self._volatile.stream_ack(stream, group, *message_ids)
        return 0

    def stream_len(self, stream: str) -> int:
        """Get the length of a stream."""
        if hasattr(self._volatile, "stream_len"):
            return self._volatile.stream_len(stream)
        return 0

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all data from all backends."""
        self._volatile.clear()
        if self._persistent is not None:
            self._persistent.clear()
        if hasattr(self._blob, "clear"):
            self._blob.clear()

    def stats(self) -> dict:
        """Return combined statistics from all backends."""
        stats = {
            "backends": {
                "volatile": self._volatile_type,
                "persistent": self._persistent_type,
                "blob": self._blob_type,
            },
            "all_redis": self._all_redis,
        }

        # Get stats from each backend
        if hasattr(self._volatile, "stats"):
            stats["volatile"] = self._volatile.stats()
        if self._persistent is not None and hasattr(self._persistent, "stats"):
            stats["persistent"] = self._persistent.stats()
        if hasattr(self._blob, "stats"):
            stats["blob"] = self._blob.stats()

        return stats

    # -------------------------------------------------------------------------
    # Timing events
    # -------------------------------------------------------------------------

    def add_timing_event(
        self,
        job_id: str,
        phase: str,
        component: str,
        timestamp: float,
        duration_ms: float | None = None,
        details: dict | None = None,
    ) -> None:
        """Add a timing event for a job."""
        if hasattr(self._volatile, "add_timing_event"):
            self._volatile.add_timing_event(
                job_id, phase, component, timestamp, duration_ms, details
            )

    def get_timing_events(self, job_id: str) -> list[dict]:
        """Get all timing events for a job."""
        if hasattr(self._volatile, "get_timing_events"):
            return self._volatile.get_timing_events(job_id)
        return []

    def clear_timing_events(self, job_id: str) -> None:
        """Clear all timing events for a job."""
        if hasattr(self._volatile, "clear_timing_events"):
            self._volatile.clear_timing_events(job_id)

    def add_timing_events_batch(
        self,
        job_id: str,
        events: list[dict],
    ) -> None:
        """Add multiple timing events in a single pipeline call."""
        if hasattr(self._volatile, "add_timing_events_batch"):
            self._volatile.add_timing_events_batch(job_id, events)

    # -------------------------------------------------------------------------
    # API request counter
    # -------------------------------------------------------------------------

    def increment_api_request_count(self, job_id: str) -> int:
        """Increment the API request counter for a job."""
        if hasattr(self._volatile, "increment_api_request_count"):
            return self._volatile.increment_api_request_count(job_id)
        return 0

    def get_api_request_count(self, job_id: str) -> int:
        """Get the total API request count for a job."""
        if hasattr(self._volatile, "get_api_request_count"):
            return self._volatile.get_api_request_count(job_id)
        return 0

    # -------------------------------------------------------------------------
    # Per-endpoint API request tracking
    # -------------------------------------------------------------------------

    def increment_api_endpoint_count(self, job_id: str, endpoint: str) -> int:
        """Increment the API request counter for a specific endpoint."""
        if hasattr(self._volatile, "increment_api_endpoint_count"):
            return self._volatile.increment_api_endpoint_count(job_id, endpoint)
        return 0

    def get_api_endpoint_counts(self, job_id: str) -> dict[str, int]:
        """Get API request counts per endpoint for a job."""
        if hasattr(self._volatile, "get_api_endpoint_counts"):
            return self._volatile.get_api_endpoint_counts(job_id)
        return {}

    # -------------------------------------------------------------------------
    # Dispatcher stats tracking
    # -------------------------------------------------------------------------

    def increment_dispatcher_flush_count(self, job_id: str, events_flushed: int) -> int:
        """Increment the dispatcher flush counter and track events flushed."""
        if hasattr(self._volatile, "increment_dispatcher_flush_count"):
            return self._volatile.increment_dispatcher_flush_count(
                job_id, events_flushed
            )
        return 0

    def get_dispatcher_stats(self, job_id: str) -> dict[str, int]:
        """Get dispatcher stats (flush_count, events_flushed, redis_calls) for a job."""
        if hasattr(self._volatile, "get_dispatcher_stats"):
            return self._volatile.get_dispatcher_stats(job_id)
        return {"flush_count": 0, "events_flushed": 0, "redis_calls": 0}

    # -------------------------------------------------------------------------
    # Redis call tracking
    # -------------------------------------------------------------------------

    def increment_redis_calls(self, job_id: str, count: int = 1) -> int:
        """Increment the Redis call counter for a job."""
        if hasattr(self._volatile, "increment_redis_calls"):
            return self._volatile.increment_redis_calls(job_id, count)
        return 0

    def get_redis_calls(self, job_id: str) -> int:
        """Get the Redis call count for a job."""
        if hasattr(self._volatile, "get_redis_calls"):
            return self._volatile.get_redis_calls(job_id)
        return 0

    def close(self) -> None:
        """Close all backend connections."""
        if hasattr(self._volatile, "close"):
            self._volatile.close()
        if self._persistent is not None and hasattr(self._persistent, "close"):
            self._persistent.close()
        if hasattr(self._blob, "close"):
            self._blob.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def __repr__(self) -> str:
        return (
            f"HybridStorage("
            f"volatile={self._volatile_type}, "
            f"persistent={self._persistent_type}, "
            f"blob={self._blob_type})"
        )

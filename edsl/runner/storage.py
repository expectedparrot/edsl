"""
Storage Protocol and Implementations

Defines the abstract storage interface and provides an in-memory implementation
for development and testing.
"""

from typing import Protocol, Any
from collections import defaultdict
import threading
import fnmatch


class StorageProtocol(Protocol):
    """
    Abstract interface for persistent/volatile key-value operations.

    Implementations can be:
    - InMemory (for testing)
    - SQLAlchemy (for single-node persistence)
    - Redis + PostgreSQL (for distributed production)
    - Firebase (for cloud-native)
    """

    # Blob operations (large binary data: FileStore content)
    def write_blob(
        self, blob_id: str, data: bytes, metadata: dict | None = None
    ) -> None:
        """Write binary blob data to blob storage."""
        ...

    def read_blob(self, blob_id: str) -> bytes | None:
        """Read binary blob data. Returns None if blob doesn't exist."""
        ...

    def read_blob_metadata(self, blob_id: str) -> dict | None:
        """Read blob metadata without reading the blob data."""
        ...

    def delete_blob(self, blob_id: str) -> None:
        """Delete a blob from storage."""
        ...

    def blob_exists(self, blob_id: str) -> bool:
        """Check if a blob exists in storage."""
        ...

    # Persistent operations (immutable data: job definitions, answers)
    def write_persistent(self, key: str, value: dict) -> None:
        """Write immutable data to persistent storage."""
        ...

    def read_persistent(self, key: str) -> dict | None:
        """Read from persistent storage. Returns None if key doesn't exist."""
        ...

    def batch_write_persistent(self, items: dict[str, dict]) -> None:
        """Write multiple items to persistent storage atomically."""
        ...

    def delete_persistent(self, key: str) -> None:
        """Delete a key from persistent storage."""
        ...

    def scan_keys_persistent(self, pattern: str) -> list[str]:
        """Scan persistent storage for keys matching pattern (glob-style)."""
        ...

    # Volatile operations (mutable data: counters, state, queues)
    def write_volatile(self, key: str, value: str | int | float | dict | list) -> None:
        """Write mutable data to volatile storage."""
        ...

    def read_volatile(self, key: str) -> str | int | float | dict | list | None:
        """Read from volatile storage. Returns None if key doesn't exist."""
        ...

    def delete_volatile(self, key: str) -> None:
        """Delete a key from volatile storage."""
        ...

    def increment_volatile(self, key: str, amount: int = 1) -> int:
        """
        Atomically increment a counter.
        Creates key with value 0 if it doesn't exist.
        Returns the new value.
        """
        ...

    def add_to_set(self, key: str, value: str) -> bool:
        """
        Add value to a set. Creates set if it doesn't exist.
        Returns True if value was added, False if already present.
        """
        ...

    def remove_from_set(self, key: str, value: str) -> bool:
        """
        Remove value from a set.
        Returns True if value was removed, False if not present.
        """
        ...

    def pop_from_set(self, key: str) -> str | None:
        """
        Atomically remove and return an arbitrary element from a set.
        Returns None if set is empty or doesn't exist.
        """
        ...

    def get_set_members(self, key: str) -> set[str]:
        """Get all members of a set. Returns empty set if key doesn't exist."""
        ...

    def set_size(self, key: str) -> int:
        """Get the number of elements in a set."""
        ...

    def scan_keys_volatile(self, pattern: str) -> list[str]:
        """Scan volatile storage for keys matching pattern (glob-style)."""
        ...

    def batch_read_volatile(
        self, keys: list[str]
    ) -> dict[str, str | int | float | dict | list | None]:
        """
        Read multiple keys from volatile storage in a single operation.
        Returns a dict mapping key to value (or None if key doesn't exist).
        """
        ...

    def batch_write_volatile(
        self, items: dict[str, str | int | float | dict | list]
    ) -> None:
        """
        Write multiple keys to volatile storage in a single operation.
        """
        ...

    def batch_read_persistent(self, keys: list[str]) -> dict[str, dict | None]:
        """
        Read multiple keys from persistent storage in a single operation.
        Returns a dict mapping key to value (or None if key doesn't exist).
        """
        ...

    def pop_multiple_from_set(self, key: str, count: int) -> list[str]:
        """
        Atomically remove and return up to count elements from a set.
        Returns empty list if set is empty or doesn't exist.
        """
        ...

    def add_multiple_to_set(self, key: str, values: list[str]) -> int:
        """
        Add multiple values to a set in a single operation.
        Returns the number of values that were actually added (not already present).
        """
        ...


class InMemoryStorage:
    """
    Thread-safe in-memory implementation of StorageProtocol.

    Suitable for:
    - Unit testing
    - Single-process development
    - Small-scale local usage

    NOT suitable for:
    - Multi-process/distributed deployment
    - Persistence across restarts
    """

    def __init__(self):
        self._persistent: dict[str, dict] = {}
        self._volatile: dict[str, Any] = {}
        self._sets: dict[str, set[str]] = defaultdict(set)
        self._blobs: dict[str, bytes] = {}
        self._blob_metadata: dict[str, dict] = {}
        self._lock = threading.RLock()

    # Blob operations

    def write_blob(
        self, blob_id: str, data: bytes, metadata: dict | None = None
    ) -> None:
        with self._lock:
            self._blobs[blob_id] = data
            self._blob_metadata[blob_id] = metadata or {}

    def read_blob(self, blob_id: str) -> bytes | None:
        with self._lock:
            return self._blobs.get(blob_id)

    def read_blob_metadata(self, blob_id: str) -> dict | None:
        with self._lock:
            return self._blob_metadata.get(blob_id)

    def delete_blob(self, blob_id: str) -> None:
        with self._lock:
            self._blobs.pop(blob_id, None)
            self._blob_metadata.pop(blob_id, None)

    def blob_exists(self, blob_id: str) -> bool:
        with self._lock:
            return blob_id in self._blobs

    # Persistent operations

    def write_persistent(self, key: str, value: dict) -> None:
        with self._lock:
            self._persistent[key] = value

    def read_persistent(self, key: str) -> dict | None:
        with self._lock:
            return self._persistent.get(key)

    def batch_write_persistent(self, items: dict[str, dict]) -> None:
        with self._lock:
            self._persistent.update(items)

    def delete_persistent(self, key: str) -> None:
        with self._lock:
            self._persistent.pop(key, None)

    def scan_keys_persistent(self, pattern: str) -> list[str]:
        with self._lock:
            return [k for k in self._persistent.keys() if fnmatch.fnmatch(k, pattern)]

    # Volatile operations

    def write_volatile(self, key: str, value: str | int | float | dict | list) -> None:
        with self._lock:
            self._volatile[key] = value

    def read_volatile(self, key: str) -> str | int | float | dict | list | None:
        with self._lock:
            return self._volatile.get(key)

    def delete_volatile(self, key: str) -> None:
        with self._lock:
            self._volatile.pop(key, None)

    def increment_volatile(self, key: str, amount: int = 1) -> int:
        with self._lock:
            current = self._volatile.get(key, 0)
            if not isinstance(current, (int, float)):
                raise TypeError(f"Cannot increment non-numeric value at key {key}")
            new_value = int(current) + amount
            self._volatile[key] = new_value
            return new_value

    def add_to_set(self, key: str, value: str) -> bool:
        with self._lock:
            if value in self._sets[key]:
                return False
            self._sets[key].add(value)
            return True

    def remove_from_set(self, key: str, value: str) -> bool:
        with self._lock:
            if value not in self._sets[key]:
                return False
            self._sets[key].discard(value)
            return True

    def pop_from_set(self, key: str) -> str | None:
        with self._lock:
            s = self._sets.get(key)
            if not s:
                return None
            return s.pop()

    def get_set_members(self, key: str) -> set[str]:
        with self._lock:
            return set(self._sets.get(key, set()))

    def set_size(self, key: str) -> int:
        with self._lock:
            return len(self._sets.get(key, set()))

    def scan_keys_volatile(self, pattern: str) -> list[str]:
        with self._lock:
            return [k for k in self._volatile.keys() if fnmatch.fnmatch(k, pattern)]

    def batch_read_volatile(
        self, keys: list[str]
    ) -> dict[str, str | int | float | dict | list | None]:
        """Read multiple keys from volatile storage in a single operation."""
        with self._lock:
            return {key: self._volatile.get(key) for key in keys}

    def batch_write_volatile(
        self, items: dict[str, str | int | float | dict | list]
    ) -> None:
        """Write multiple keys to volatile storage in a single operation."""
        with self._lock:
            self._volatile.update(items)

    def batch_read_persistent(self, keys: list[str]) -> dict[str, dict | None]:
        """Read multiple keys from persistent storage in a single operation."""
        with self._lock:
            return {key: self._persistent.get(key) for key in keys}

    def pop_multiple_from_set(self, key: str, count: int) -> list[str]:
        """Atomically remove and return up to count elements from a set."""
        with self._lock:
            s = self._sets.get(key)
            if not s:
                return []
            result = []
            for _ in range(min(count, len(s))):
                if s:
                    result.append(s.pop())
            return result

    def add_multiple_to_set(self, key: str, values: list[str]) -> int:
        """Add multiple values to a set in a single operation."""
        with self._lock:
            existing = self._sets[key]
            new_values = set(values) - existing
            self._sets[key].update(new_values)
            return len(new_values)

    # Utility methods for testing/debugging

    def clear(self) -> None:
        """Clear all data from storage."""
        with self._lock:
            self._persistent.clear()
            self._volatile.clear()
            self._sets.clear()
            self._blobs.clear()
            self._blob_metadata.clear()

    def stats(self) -> dict:
        """Return storage statistics."""
        with self._lock:
            return {
                "persistent_keys": len(self._persistent),
                "volatile_keys": len(self._volatile),
                "sets": len(self._sets),
                "total_set_members": sum(len(s) for s in self._sets.values()),
                "blobs": len(self._blobs),
                "total_blob_size": sum(len(b) for b in self._blobs.values()),
            }

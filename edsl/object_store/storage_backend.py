"""Storage backend protocol for CAS repositories.

Abstracts file I/O so that :class:`CASRepository` can work with local
filesystems, GCS, S3, or any other key-value store.
"""

from __future__ import annotations

from typing import Iterator, Protocol, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """Protocol for blob/file storage.

    Keys are relative paths like ``"blobs/abc123.json"`` or ``"refs/main"``.
    """

    def read(self, key: str) -> str:
        """Read content at *key*.  Raises :class:`KeyError` if not found."""
        ...

    def write(self, key: str, content: str) -> None:
        """Write *content* at *key*, creating intermediate structure as needed."""
        ...

    def exists(self, key: str) -> bool:
        """Return ``True`` if *key* exists."""
        ...

    def delete(self, key: str) -> None:
        """Delete *key*.  No-op if not found."""
        ...

    def list_prefix(self, prefix: str) -> Iterator[str]:
        """Yield all keys that start with *prefix*.

        Example: ``list_prefix("refs/")`` -> ``["refs/main", "refs/experiment"]``
        """
        ...

    def delete_tree(self, prefix: str) -> None:
        """Delete all keys under *prefix* (recursive remove)."""
        ...

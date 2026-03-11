"""Metadata index protocol for the CAS object store.

Abstracts object listing, commit history, user management, and
token-based authentication so the store doesn't need to scan
directories or walk commit chains.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class MetadataIndex(Protocol):
    """Protocol for indexing object metadata and commit history."""

    # ------------------------------------------------------------------
    # Object metadata
    # ------------------------------------------------------------------

    def put(self, uuid: str, meta: dict, owner: Optional[str] = None) -> None:
        """Insert or update metadata for an object.

        *owner* is recorded on INSERT only (immutable once set).
        """
        ...

    def get(self, uuid: str) -> Optional[dict]:
        """Get metadata for a single object, or ``None``."""
        ...

    def delete(self, uuid: str) -> None:
        """Remove metadata (and commit history) for an object."""
        ...

    def list_all(self, owner: Optional[str] = None) -> list[dict]:
        """Return metadata for all objects (each dict includes ``uuid``).

        If *owner* is given, filter to that user's objects.
        """
        ...

    def search(
        self,
        type_name: Optional[str] = None,
        query: Optional[str] = None,
        owner: Optional[str] = None,
    ) -> list[dict]:
        """Filter objects by type, text search, and/or owner."""
        ...

    # ------------------------------------------------------------------
    # Ownership
    # ------------------------------------------------------------------

    def get_owner(self, uuid: str) -> Optional[str]:
        """Return the owner username for an object, or ``None``."""
        ...

    def set_owner(self, uuid: str, username: str) -> None:
        """Set the owner of an object (for claiming unowned objects)."""
        ...

    # ------------------------------------------------------------------
    # Commit history
    # ------------------------------------------------------------------

    def put_commit(
        self,
        uuid: str,
        commit_hash: str,
        commit_data: dict,
    ) -> None:
        """Record a commit in the index.

        *commit_data* should contain ``parent``, ``tree``, ``timestamp``,
        ``message``, and ``branch``.
        """
        ...

    def log(
        self,
        uuid: str,
        branch: Optional[str] = None,
        limit: int = 0,
    ) -> list[dict]:
        """Return commit history for an object, newest first.

        If *branch* is given, only return commits reachable from that
        branch's tip.  If *limit* > 0, return at most that many entries.
        """
        ...

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    def create_user(self, username: str) -> dict:
        """Create a user. Returns ``{"username": ..., "created": ...}``."""
        ...

    def get_user(self, username: str) -> Optional[dict]:
        """Get user by username, or ``None``."""
        ...

    def list_users(self) -> list[dict]:
        """Return all users."""
        ...

    # ------------------------------------------------------------------
    # Token management
    # ------------------------------------------------------------------

    def create_token(self, username: str) -> str:
        """Create and return an opaque bearer token for *username*."""
        ...

    def validate_token(self, token: str) -> Optional[str]:
        """Return the username for a valid token, or ``None``."""
        ...

    def revoke_token(self, token: str) -> None:
        """Delete a token."""
        ...

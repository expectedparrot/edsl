"""
Utility functions for object versioning.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
import hashlib
import json


def _utcnow() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


def _sha256(b: bytes) -> str:
    """Return SHA256 hex digest of bytes."""
    return hashlib.sha256(b).hexdigest()


def _stable_dumps(obj: Any) -> bytes:
    """
    Canonical JSON bytes for hashing.

    Raises TypeError for non-JSON-serializable types to prevent hash collisions.
    """
    try:
        return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    except TypeError as e:
        raise TypeError(
            f"State must be JSON-serializable. Got non-serializable value: {e}. "
            f"Use to_dict()/from_dict() to convert complex types."
        ) from e

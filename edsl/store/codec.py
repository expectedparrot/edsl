"""
Codec Protocol for encoding/decoding domain objects.

Created: 2026-01-08
"""

from __future__ import annotations
from typing import Any, Protocol, TypeVar

T = TypeVar("T")


class Codec(Protocol[T]):
    """Protocol for encoding/decoding domain objects to/from primitives.

    Implementations of this protocol convert between domain objects and
    JSON-serializable dictionaries, enabling storage and retrieval of
    typed data in the Store.

    Example implementation:
        class MyCodec:
            def encode(self, obj: MyClass) -> dict[str, Any]:
                return obj.to_dict()

            def decode(self, data: dict[str, Any]) -> MyClass:
                return MyClass.from_dict(data)
    """

    def encode(self, obj: T) -> dict[str, Any]:
        """Convert domain object to JSON-serializable dict."""
        ...

    def decode(self, data: dict[str, Any]) -> T:
        """Convert dict back to domain object."""
        ...

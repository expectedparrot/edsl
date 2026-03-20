"""Backward-compatibility re-export.

The store accessor now lives at :mod:`edsl.base.store_accessor`.
"""

from edsl.base.store_accessor import (
    StoreDescriptor,
    ClassStoreAccessor,
    InstanceStoreAccessor,
)

__all__ = ["StoreDescriptor", "ClassStoreAccessor", "InstanceStoreAccessor"]

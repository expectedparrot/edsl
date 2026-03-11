"""CAS-backed object store package.

Re-exports the public API so that ``from edsl.object_store import ObjectStore``
(and the relative ``from ..object_store import ObjectStore`` used by
``store_accessor``) continue to work.
"""

from .store import ObjectStore
from .cas_repository import CASRepository
from .exceptions import StaleBranchError
from .storage_backend import StorageBackend
from .fs_backend import FileSystemBackend
from .http_backend import HttpBackend
from .metadata_index import MetadataIndex
from .sqlite_metadata_index import SQLiteMetadataIndex

__all__ = [
    "ObjectStore",
    "CASRepository",
    "StaleBranchError",
    "StorageBackend",
    "FileSystemBackend",
    "HttpBackend",
    "MetadataIndex",
    "SQLiteMetadataIndex",
]

"""CAS-backed object store internals."""

from .store import ObjectStore
from .cas_repository import CASRepository
from .exceptions import AmbiguousUUIDError, StaleBranchError
from .storage_backend import StorageBackend
from .fs_backend import FileSystemBackend
from .http_backend import HttpBackend
from .metadata_index import MetadataIndex
from .sqlite_metadata_index import SQLiteMetadataIndex
from .store_info import StoreSaveInfo, StoreListInfo, StoreLogInfo, StoreDiffInfo
from .streaming_writer import StreamingCASWriter

__all__ = [
    "ObjectStore",
    "CASRepository",
    "AmbiguousUUIDError",
    "StaleBranchError",
    "StorageBackend",
    "FileSystemBackend",
    "HttpBackend",
    "MetadataIndex",
    "SQLiteMetadataIndex",
    "StoreSaveInfo",
    "StoreListInfo",
    "StoreLogInfo",
    "StoreDiffInfo",
    "StreamingCASWriter",
]


def _lazy_gcs_backend():
    from .gcs_backend import GCSBackend
    return GCSBackend


def _lazy_pg_metadata_index():
    from .pg_metadata_index import PostgreSQLMetadataIndex
    return PostgreSQLMetadataIndex

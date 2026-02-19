"""
SQLAlchemy Storage Implementation

Provides a database-backed implementation of StorageProtocol using SQLAlchemy.
Supports SQLite (for development/testing) and PostgreSQL (for production).

Thread Safety:
- SQLite: Uses a threading lock to serialize all database operations
- PostgreSQL: Relies on database-level locking (row-level locks, transactions)
"""

import json
import fnmatch
import logging
import threading
import time
from typing import Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Thread-local storage for tracking DB operations
_db_stats = threading.local()


def reset_db_stats():
    """Reset DB operation counters for the current thread."""
    _db_stats.calls = 0
    _db_stats.start_time = time.time()


def get_db_stats():
    """Get DB operation stats for the current thread."""
    calls = getattr(_db_stats, "calls", 0)
    start_time = getattr(_db_stats, "start_time", None)
    elapsed = (time.time() - start_time) * 1000 if start_time else 0
    return {"calls": calls, "elapsed_ms": elapsed}


def _track_db_call():
    """Increment DB call counter."""
    if not hasattr(_db_stats, "calls"):
        _db_stats.calls = 0
    _db_stats.calls += 1


from sqlalchemy import (
    create_engine,
    Column,
    String,
    Integer,
    Float,
    LargeBinary,
    Text,
    Index,
    UniqueConstraint,
    event,
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session, scoped_session
from sqlalchemy.pool import StaticPool, NullPool, QueuePool
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

Base = declarative_base()


class PersistentData(Base):
    """Table for immutable persistent data (job definitions, answers, etc.)."""

    __tablename__ = "persistent_data"

    key = Column(String(512), primary_key=True)
    value = Column(Text, nullable=False)  # JSON-encoded

    __table_args__ = (Index("ix_persistent_key_prefix", key),)


class VolatileData(Base):
    """Table for mutable volatile data (counters, state, etc.)."""

    __tablename__ = "volatile_data"

    key = Column(String(512), primary_key=True)
    value = Column(Text, nullable=False)  # JSON-encoded
    value_type = Column(
        String(32), nullable=False
    )  # 'int', 'float', 'str', 'dict', 'list'

    __table_args__ = (Index("ix_volatile_key_prefix", key),)


class SetData(Base):
    """Table for set operations (ready task sets, etc.)."""

    __tablename__ = "set_data"

    id = Column(Integer, primary_key=True, autoincrement=True)
    set_key = Column(String(512), nullable=False, index=True)
    member = Column(String(512), nullable=False)

    __table_args__ = (
        UniqueConstraint("set_key", "member", name="uq_set_member"),
        Index("ix_set_key", set_key),
    )


class BlobData(Base):
    """Table for large binary data (FileStore content, etc.)."""

    __tablename__ = "blob_data"

    blob_id = Column(String(512), primary_key=True)
    data = Column(LargeBinary, nullable=False)
    blob_metadata = Column(Text, nullable=True)  # JSON-encoded


class SQLAlchemyStorage:
    """
    SQLAlchemy implementation of StorageProtocol.

    Suitable for:
    - Single-node persistence with SQLite
    - Multi-node deployment with PostgreSQL
    - Development and production use

    Thread Safety:
    - SQLite uses a threading lock to serialize all operations
    - For in-memory SQLite, uses StaticPool to share the connection across threads
    - PostgreSQL relies on native database locking

    Usage:
        # SQLite (development)
        storage = SQLAlchemyStorage("sqlite:///runner.db")

        # PostgreSQL (production)
        storage = SQLAlchemyStorage("postgresql://user:pass@host/dbname")

        # In-memory SQLite (testing) - thread-safe
        storage = SQLAlchemyStorage("sqlite:///:memory:")
    """

    def __init__(
        self,
        connection_string: str = "sqlite:///runner.db",
        echo: bool = False,
        pool_size: int = None,
        max_overflow: int = None,
        use_null_pool: bool = None,
    ):
        """
        Initialize SQLAlchemy storage.

        Args:
            connection_string: SQLAlchemy connection URL
            echo: If True, log all SQL statements (for debugging)
            pool_size: Number of connections to keep in pool (default: 2 for PostgreSQL)
            max_overflow: Max connections above pool_size (default: 3 for PostgreSQL)
            use_null_pool: If True, use NullPool (no persistent connections).
                          Recommended for serverless environments like Cloud Run.
                          Can also be set via DB_USE_NULL_POOL=true environment variable.
        """
        import os

        self._is_sqlite = "sqlite" in connection_string
        self._is_postgres = "postgresql" in connection_string
        self._is_memory = ":memory:" in connection_string

        # Threading lock for SQLite (which doesn't handle concurrent writes well)
        self._lock = threading.RLock() if self._is_sqlite else None

        # Check environment variables for pool configuration
        if use_null_pool is None:
            use_null_pool = os.environ.get("DB_USE_NULL_POOL", "").lower() in (
                "true",
                "1",
                "yes",
            )
        if pool_size is None:
            pool_size = int(os.environ.get("DB_POOL_SIZE", "2"))
        if max_overflow is None:
            max_overflow = int(os.environ.get("DB_MAX_OVERFLOW", "3"))

        # Configure engine based on database type
        if self._is_sqlite:
            if self._is_memory:
                # In-memory SQLite: use StaticPool so all threads share the same connection
                self._engine = create_engine(
                    connection_string,
                    echo=echo,
                    connect_args={"check_same_thread": False},
                    poolclass=StaticPool,
                )
            else:
                # File-based SQLite: use standard pooling with check_same_thread=False
                self._engine = create_engine(
                    connection_string,
                    echo=echo,
                    connect_args={"check_same_thread": False},
                )

            # Enable WAL mode for file-based SQLite (better concurrency)
            if not self._is_memory:

                @event.listens_for(self._engine, "connect")
                def set_sqlite_pragma(dbapi_connection, connection_record):
                    cursor = dbapi_connection.cursor()
                    cursor.execute("PRAGMA journal_mode=WAL")
                    cursor.execute("PRAGMA synchronous=NORMAL")
                    cursor.close()

        else:
            # PostgreSQL or other databases
            # Configure connection pooling for serverless/cloud environments
            if use_null_pool:
                # NullPool: No persistent connections - best for serverless (Cloud Run, Lambda)
                # Each operation opens a new connection and closes it immediately
                self._engine = create_engine(
                    connection_string,
                    echo=echo,
                    poolclass=NullPool,
                )
            else:
                # QueuePool with small pool size - for traditional deployments
                # Default: 2 connections + 3 overflow = max 5 per instance
                self._engine = create_engine(
                    connection_string,
                    echo=echo,
                    poolclass=QueuePool,
                    pool_size=pool_size,
                    max_overflow=max_overflow,
                    pool_pre_ping=True,  # Verify connections before use
                    pool_recycle=300,  # Recycle connections every 5 minutes
                )

        self._Session = sessionmaker(bind=self._engine)

        # Create tables (handle race condition with concurrent services)
        try:
            Base.metadata.create_all(self._engine, checkfirst=True)
        except Exception as e:
            # Tables may already exist due to concurrent creation
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                pass  # Tables exist, that's fine
            else:
                raise

    @contextmanager
    def _session(self) -> Session:
        """Context manager for database sessions with thread-safe locking."""
        # Acquire lock for SQLite
        if self._lock:
            self._lock.acquire()

        session = self._Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
            # Release lock for SQLite
            if self._lock:
                self._lock.release()

    # -------------------------------------------------------------------------
    # Blob operations
    # -------------------------------------------------------------------------

    def write_blob(
        self, blob_id: str, data: bytes, metadata: dict | None = None
    ) -> None:
        """Write binary blob data to blob storage."""
        with self._session() as session:
            metadata_json = json.dumps(metadata) if metadata else None

            if self._is_postgres:
                stmt = (
                    pg_insert(BlobData)
                    .values(blob_id=blob_id, data=data, blob_metadata=metadata_json)
                    .on_conflict_do_update(
                        index_elements=["blob_id"],
                        set_={"data": data, "blob_metadata": metadata_json},
                    )
                )
                session.execute(stmt)
            else:
                stmt = (
                    sqlite_insert(BlobData)
                    .values(blob_id=blob_id, data=data, blob_metadata=metadata_json)
                    .on_conflict_do_update(
                        index_elements=["blob_id"],
                        set_={"data": data, "blob_metadata": metadata_json},
                    )
                )
                session.execute(stmt)

    def read_blob(self, blob_id: str) -> bytes | None:
        """Read binary blob data. Returns None if blob doesn't exist."""
        with self._session() as session:
            result = (
                session.query(BlobData.data).filter(BlobData.blob_id == blob_id).first()
            )
            return result[0] if result else None

    def read_blob_metadata(self, blob_id: str) -> dict | None:
        """Read blob metadata without reading the blob data."""
        with self._session() as session:
            result = (
                session.query(BlobData.blob_metadata)
                .filter(BlobData.blob_id == blob_id)
                .first()
            )
            if result and result[0]:
                return json.loads(result[0])
            return None

    def delete_blob(self, blob_id: str) -> None:
        """Delete a blob from storage."""
        with self._session() as session:
            session.query(BlobData).filter(BlobData.blob_id == blob_id).delete()

    def blob_exists(self, blob_id: str) -> bool:
        """Check if a blob exists in storage."""
        with self._session() as session:
            result = (
                session.query(BlobData.blob_id)
                .filter(BlobData.blob_id == blob_id)
                .first()
            )
            return result is not None

    # -------------------------------------------------------------------------
    # Persistent operations
    # -------------------------------------------------------------------------

    def write_persistent(self, key: str, value: dict) -> None:
        """Write immutable data to persistent storage."""
        t0 = time.time()
        with self._session() as session:
            value_json = json.dumps(value)

            if self._is_postgres:
                stmt = (
                    pg_insert(PersistentData)
                    .values(key=key, value=value_json)
                    .on_conflict_do_update(
                        index_elements=["key"], set_={"value": value_json}
                    )
                )
                session.execute(stmt)
            else:
                stmt = (
                    sqlite_insert(PersistentData)
                    .values(key=key, value=value_json)
                    .on_conflict_do_update(
                        index_elements=["key"], set_={"value": value_json}
                    )
                )
                session.execute(stmt)
            _track_db_call()

        elapsed_ms = (time.time() - t0) * 1000
        logger.debug(f"[DB] write_persistent: {key[:50]}... {elapsed_ms:.1f}ms")

    def read_persistent(self, key: str) -> dict | None:
        """Read from persistent storage. Returns None if key doesn't exist."""
        with self._session() as session:
            result = (
                session.query(PersistentData.value)
                .filter(PersistentData.key == key)
                .first()
            )
            if result:
                return json.loads(result[0])
            return None

    def batch_write_persistent(self, items: dict[str, dict]) -> None:
        """
        Write multiple items to persistent storage atomically.

        Uses TRUE BULK INSERT - one SQL statement for all items.
        This reduces N network round-trips to 1, dramatically improving
        performance on high-latency connections (e.g., GCP Cloud Run).
        """
        if not items:
            return

        n_items = len(items)
        t0 = time.time()

        # Build list of all values for bulk insert
        values_list = [
            {"key": key, "value": json.dumps(value)} for key, value in items.items()
        ]

        with self._session() as session:
            if self._is_postgres:
                # PostgreSQL: Single INSERT with all VALUES, ON CONFLICT DO UPDATE
                stmt = pg_insert(PersistentData).values(values_list)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["key"], set_={"value": stmt.excluded.value}
                )
                session.execute(stmt)
            else:
                # SQLite: Single INSERT with all VALUES, ON CONFLICT DO UPDATE
                stmt = sqlite_insert(PersistentData).values(values_list)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["key"], set_={"value": stmt.excluded.value}
                )
                session.execute(stmt)

            _track_db_call()

        elapsed_ms = (time.time() - t0) * 1000
        logger.info(
            f"[DB] batch_write_persistent: {n_items} items, 1 DB call (BULK), {elapsed_ms:.1f}ms total"
        )

    def batch_read_persistent(self, keys: list[str]) -> dict[str, dict | None]:
        """Read multiple keys from persistent storage in a single query."""
        if not keys:
            return {}

        with self._session() as session:
            results = (
                session.query(PersistentData.key, PersistentData.value)
                .filter(PersistentData.key.in_(keys))
                .all()
            )

            # Build result dict from query results
            found = {row[0]: json.loads(row[1]) for row in results}

            # Return dict with all requested keys (None for missing)
            return {key: found.get(key) for key in keys}

    def delete_persistent(self, key: str) -> None:
        """Delete a key from persistent storage."""
        with self._session() as session:
            session.query(PersistentData).filter(PersistentData.key == key).delete()

    def scan_keys_persistent(self, pattern: str) -> list[str]:
        """Scan persistent storage for keys matching pattern (glob-style)."""
        with self._session() as session:
            # Convert glob pattern to SQL LIKE pattern for prefix optimization
            sql_prefix = pattern.split("*")[0] if "*" in pattern else pattern

            if sql_prefix:
                results = (
                    session.query(PersistentData.key)
                    .filter(PersistentData.key.like(f"{sql_prefix}%"))
                    .all()
                )
            else:
                results = session.query(PersistentData.key).all()

            # Apply full glob matching in Python
            return [r[0] for r in results if fnmatch.fnmatch(r[0], pattern)]

    # -------------------------------------------------------------------------
    # Volatile operations
    # -------------------------------------------------------------------------

    def _encode_volatile(self, value: Any) -> tuple[str, str]:
        """Encode a volatile value to JSON string and type."""
        if isinstance(value, int):
            return json.dumps(value), "int"
        elif isinstance(value, float):
            return json.dumps(value), "float"
        elif isinstance(value, str):
            return json.dumps(value), "str"
        elif isinstance(value, dict):
            return json.dumps(value), "dict"
        elif isinstance(value, list):
            return json.dumps(value), "list"
        else:
            return json.dumps(value), "unknown"

    def _decode_volatile(self, value_json: str, value_type: str) -> Any:
        """Decode a volatile value from JSON string."""
        value = json.loads(value_json)
        if value_type == "int":
            return int(value)
        elif value_type == "float":
            return float(value)
        return value

    def write_volatile(self, key: str, value: str | int | float | dict | list) -> None:
        """Write mutable data to volatile storage."""
        with self._session() as session:
            value_json, value_type = self._encode_volatile(value)

            if self._is_postgres:
                stmt = (
                    pg_insert(VolatileData)
                    .values(key=key, value=value_json, value_type=value_type)
                    .on_conflict_do_update(
                        index_elements=["key"],
                        set_={"value": value_json, "value_type": value_type},
                    )
                )
                session.execute(stmt)
            else:
                stmt = (
                    sqlite_insert(VolatileData)
                    .values(key=key, value=value_json, value_type=value_type)
                    .on_conflict_do_update(
                        index_elements=["key"],
                        set_={"value": value_json, "value_type": value_type},
                    )
                )
                session.execute(stmt)

    def read_volatile(self, key: str) -> str | int | float | dict | list | None:
        """Read from volatile storage. Returns None if key doesn't exist."""
        with self._session() as session:
            result = (
                session.query(VolatileData.value, VolatileData.value_type)
                .filter(VolatileData.key == key)
                .first()
            )
            if result:
                return self._decode_volatile(result[0], result[1])
            return None

    def delete_volatile(self, key: str) -> None:
        """Delete a key from volatile storage."""
        with self._session() as session:
            session.query(VolatileData).filter(VolatileData.key == key).delete()

    def increment_volatile(self, key: str, amount: int = 1) -> int:
        """Atomically increment a counter."""
        with self._session() as session:
            result = (
                session.query(VolatileData)
                .filter(VolatileData.key == key)
                .with_for_update()
                .first()
            )

            if result is None:
                new_value = amount
                session.add(
                    VolatileData(key=key, value=json.dumps(new_value), value_type="int")
                )
            else:
                current = self._decode_volatile(result.value, result.value_type)
                if not isinstance(current, (int, float)):
                    raise TypeError(f"Cannot increment non-numeric value at key {key}")
                new_value = int(current) + amount
                result.value = json.dumps(new_value)
                result.value_type = "int"

            return new_value

    def scan_keys_volatile(self, pattern: str) -> list[str]:
        """Scan volatile storage for keys matching pattern (glob-style)."""
        with self._session() as session:
            sql_prefix = pattern.split("*")[0] if "*" in pattern else pattern

            if sql_prefix:
                results = (
                    session.query(VolatileData.key)
                    .filter(VolatileData.key.like(f"{sql_prefix}%"))
                    .all()
                )
            else:
                results = session.query(VolatileData.key).all()

            return [r[0] for r in results if fnmatch.fnmatch(r[0], pattern)]

    # -------------------------------------------------------------------------
    # Set operations
    # -------------------------------------------------------------------------

    def add_to_set(self, key: str, value: str) -> bool:
        """Add value to a set. Returns True if value was added, False if already present."""
        with self._session() as session:
            existing = (
                session.query(SetData)
                .filter(SetData.set_key == key, SetData.member == value)
                .first()
            )

            if existing:
                return False

            session.add(SetData(set_key=key, member=value))
            return True

    def remove_from_set(self, key: str, value: str) -> bool:
        """Remove value from a set. Returns True if value was removed."""
        with self._session() as session:
            deleted = (
                session.query(SetData)
                .filter(SetData.set_key == key, SetData.member == value)
                .delete()
            )
            return deleted > 0

    def pop_from_set(self, key: str) -> str | None:
        """Atomically remove and return an arbitrary element from a set."""
        with self._session() as session:
            result = (
                session.query(SetData)
                .filter(SetData.set_key == key)
                .with_for_update()
                .first()
            )

            if result is None:
                return None

            member = result.member
            session.delete(result)
            return member

    def get_set_members(self, key: str) -> set[str]:
        """Get all members of a set."""
        with self._session() as session:
            results = session.query(SetData.member).filter(SetData.set_key == key).all()
            return {r[0] for r in results}

    def set_size(self, key: str) -> int:
        """Get the number of elements in a set."""
        with self._session() as session:
            return session.query(SetData).filter(SetData.set_key == key).count()

    # -------------------------------------------------------------------------
    # Utility methods
    # -------------------------------------------------------------------------

    def clear(self) -> None:
        """Clear all data from storage."""
        with self._session() as session:
            session.query(PersistentData).delete()
            session.query(VolatileData).delete()
            session.query(SetData).delete()
            session.query(BlobData).delete()

    def stats(self) -> dict:
        """Return storage statistics."""
        with self._session() as session:
            return {
                "persistent_keys": session.query(PersistentData).count(),
                "volatile_keys": session.query(VolatileData).count(),
                "set_entries": session.query(SetData).count(),
                "unique_sets": session.query(SetData.set_key).distinct().count(),
                "blobs": session.query(BlobData).count(),
            }

    def close(self) -> None:
        """Close the database connection."""
        self._engine.dispose()

"""
SQLite-backed dictionary implementation for persistent storage of cache entries.

This module provides a dictionary-like interface to an SQLite database, which allows
for efficient, persistent storage of cache entries. SQLiteDict implements standard
dictionary methods like __getitem__, __setitem__, keys(), values(), and items(),
making it a drop-in replacement for regular dictionaries but with database persistence.
"""

from __future__ import annotations
import json
from typing import Any, Generator, Optional, Union, Dict, TypeVar

from ..config import CONFIG
from .cache_entry import CacheEntry
from .orm import Data

T = TypeVar('T')


class SQLiteDict:
    """
    Dictionary-like interface for SQLite database storage of cache entries.
    
    SQLiteDict provides a dictionary-like interface to an SQLite database, allowing
    for persistent storage of CacheEntry objects. It implements all the standard
    dictionary methods, making it a drop-in replacement for in-memory dictionaries
    when persistence is needed.
    
    The primary use case is for storing cache entries that should persist across
    program invocations, with keys being the hash of the cache entry's content and
    values being the CacheEntry objects themselves.
    
    Attributes:
        db_path (str): Path to the SQLite database file
        engine: SQLAlchemy engine instance for database access
        Session: SQLAlchemy sessionmaker for creating database sessions
        
    Example:
        >>> temp_db_path = SQLiteDict._get_temp_path()
        >>> cache = SQLiteDict(temp_db_path)
        >>> entry = CacheEntry.example()
        >>> cache[entry.key] = entry
        >>> retrieved_entry = cache[entry.key]
        >>> entry == retrieved_entry
        True
        >>> import os; os.unlink(temp_db_path)  # Clean up temp file
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Initializes a SQLiteDict with the specified database path.
        
        This constructor creates a new SQLiteDict instance connected to the
        specified SQLite database. If no database path is provided, it uses
        the path from the EDSL configuration.
        
        Args:
            db_path: Path to the SQLite database file. If None, uses the path
                    from CONFIG.get("EDSL_DATABASE_PATH")
                    
        Raises:
            Exception: If there is an error initializing the database connection
            
        Example:
            >>> temp_db_path = SQLiteDict._get_temp_path()
            >>> db = SQLiteDict(f"sqlite:///{temp_db_path}")  # Use the temp file for SQLite
            >>> isinstance(db, SQLiteDict)
            True
            >>> import os; os.unlink(temp_db_path)  # Clean up the temp file after the test
        """
        from sqlalchemy.exc import SQLAlchemyError
        from sqlalchemy.orm import sessionmaker
        from sqlalchemy import create_engine

        self.db_path = db_path or CONFIG.get("EDSL_DATABASE_PATH")
        if not self.db_path.startswith("sqlite:///"):
            self.db_path = f"sqlite:///{self.db_path}"
        try:
            from .orm import Base

            self.engine = create_engine(self.db_path, echo=False, future=True)
            Base.metadata.create_all(self.engine)
            self.Session = sessionmaker(bind=self.engine)
        except SQLAlchemyError as e:
            from .exceptions import CacheError
            raise CacheError(
                f"""Database initialization error: {e}. The attempted DB path was {db_path}"""
            ) from e

    @classmethod
    def _get_temp_path(cls) -> str:
        """
        Creates a temporary file path for a SQLite database.
        
        This helper method generates a temporary file path suitable for
        creating a temporary SQLite database file. It's primarily used
        for testing and examples.
        
        Returns:
            Path to a temporary file location
        """
        import tempfile

        _, temp_db_path = tempfile.mkstemp(suffix=".db")
        return temp_db_path

    def __setitem__(self, key: str, value: CacheEntry) -> None:
        """
        Stores a CacheEntry object at the specified key.
        
        This method stores a CacheEntry object in the database, using the
        specified key. The value is serialized to JSON before storage.
        
        Args:
            key: The key to store the value under
            value: The CacheEntry object to store
            
        Raises:
            ValueError: If the value is not a CacheEntry object
            
        Example:
            >>> d = SQLiteDict.example()
            >>> d["foo"] = CacheEntry.example()
        """
        if not isinstance(value, CacheEntry):
            from .exceptions import CacheValueError
            raise CacheValueError(f"Value must be a CacheEntry object (got {type(value)}).")
        with self.Session() as db:
            from .orm import Data

            db.merge(Data(key=key, value=json.dumps(value.to_dict())))
            db.commit()

    def __getitem__(self, key: str) -> CacheEntry:
        """
        Retrieves a CacheEntry object for the specified key.
        
        This method retrieves a CacheEntry object from the database using
        the specified key. The stored JSON value is deserialized into a
        CacheEntry object.
        
        Args:
            key: The key to retrieve the value for
            
        Returns:
            The CacheEntry object stored at the specified key
            
        Raises:
            KeyError: If the key is not found in the database
            
        Example:
            >>> d = SQLiteDict.example()
            >>> d["foo"] = CacheEntry.example()
            >>> d["foo"] == CacheEntry.example()
            True
        """
        with self.Session() as db:
            from .orm import Data

            value = db.query(Data).filter_by(key=key).first()
            if not value:
                from .exceptions import CacheKeyError
                raise CacheKeyError(f"Key '{key}' not found.")
            return CacheEntry.from_dict(json.loads(value.value))

    def get(self, key: str, default: Optional[Any] = None) -> Union[CacheEntry, Any]:
        """
        Retrieves a value for the specified key with a default fallback.
        
        This method attempts to retrieve a CacheEntry for the specified key,
        returning a default value if the key is not found. This provides a
        safer alternative to __getitem__ when the key might not exist.
        
        Args:
            key: The key to retrieve the value for
            default: The value to return if the key is not found (default: None)
            
        Returns:
            The CacheEntry for the key if found, otherwise the default value
            
        Example:
            >>> d = SQLiteDict.example()
            >>> d.get("foo", "bar")
            'bar'
        """
        from .exceptions import CacheKeyError
        try:
            return self[key]
        except (KeyError, CacheKeyError):
            return default

    def __bool__(self) -> bool:
        """
        Always returns True for SQLiteDict instances.
        
        This special method ensures that SQLiteDict objects are always truthy
        in boolean contexts, which allows patterns like `cache = cache or SQLiteDict()`
        to work as expected.
        
        Returns:
            Always True for any SQLiteDict instance
        """
        return True

    def update(
        self,
        new_d: Union[Dict[str, CacheEntry], SQLiteDict],
        overwrite: bool = False,
        max_batch_size: int = 100,
    ) -> None:
        """
        Updates the dictionary with values from another dictionary or SQLiteDict.
        
        This method adds entries from another dictionary or SQLiteDict to this
        SQLiteDict. It optionally overwrites existing entries and uses batched
        transactions for efficiency when updating many entries.
        
        Args:
            new_d: The dictionary or SQLiteDict containing entries to add
            overwrite: If True, overwrites existing entries; if False, keeps
                       existing entries unchanged (default: False)
            max_batch_size: Maximum number of entries to update in a single
                           database transaction (default: 100)
                           
        Raises:
            ValueError: If new_d is not a dict or SQLiteDict
            
        Example:
            >>> d = SQLiteDict.example()
            >>> d.update({"foo": CacheEntry.example()})
            >>> d["foo"] == CacheEntry.example()
            True
        
        Note:
            For large updates, the batched transaction approach helps prevent
            the database from being locked for too long.
        """
        if not (isinstance(new_d, dict) or isinstance(new_d, SQLiteDict)):
            from .exceptions import CacheValueError
            raise CacheValueError(
                f"new_d must be a dict or SQLiteDict object (got {type(new_d)})"
            )
        current_batch = 0
        with self.Session() as db:
            for key, value in new_d.items():
                if current_batch == max_batch_size:
                    db.commit()
                    current_batch = 0
                current_batch += 1
                # Only merge if key doesn't exist or overwrite is True
                if (key in self and overwrite) or key not in self:
                    db.merge(Data(key=key, value=json.dumps(value.to_dict())))
            db.commit()

    def values(self) -> Generator[CacheEntry, None, None]:
        """
        Returns a generator that yields the values in the cache.

        >>> d = SQLiteDict.example()
        >>> d["foo"] = CacheEntry.example()
        >>> list(d.values()) == [CacheEntry.example()]
        True
        """
        with self.Session() as db:
            for instance in db.query(Data).all():
                yield CacheEntry.from_dict(json.loads(instance.value))

    def items(self) -> Generator[tuple[str, CacheEntry], None, None]:
        """
        Returns a generator that yields the items in the cache.

        >>> d = SQLiteDict.example()
        >>> d["foo"] = CacheEntry.example()
        >>> list(d.items()) == [("foo", CacheEntry.example())]
        True
        """
        with self.Session() as db:
            for instance in db.query(Data).all():
                yield (instance.key, CacheEntry.from_dict(json.loads(instance.value)))

    def to_dict(self):
        """
        Returns the cache as a dictionary.

        >>> d = SQLiteDict.example()
        >>> d["foo"] = CacheEntry.example()
        >>> d.to_dict() == {"foo": CacheEntry.example()}
        True
        """
        return dict(self.items())

    def __delitem__(self, key: str) -> None:
        """
        Deletes the value for a given key.

        >>> d = SQLiteDict.example()
        >>> d["foo"] = CacheEntry.example()
        >>> del d["foo"]
        >>> d.get("foo", "missing")
        'missing'
        """
        with self.Session() as db:
            instance = db.query(Data).filter_by(key=key).one_or_none()
            if instance:
                db.delete(instance)
                db.commit()
            else:
                from .exceptions import CacheKeyError
                raise CacheKeyError(f"Key '{key}' not found.")

    def __contains__(self, key: str) -> bool:
        """
        Checks if the dict contains the given key.

        >>> d = SQLiteDict.example()
        >>> d["foo"] = CacheEntry.example()
        >>> "foo" in d
        True
        >>> "bar" in d
        False
        """
        with self.Session() as db:
            return db.query(Data).filter_by(key=key).first() is not None

    def __iter__(self) -> Generator[str, None, None]:
        """
        Returns a generator that yields the keys in the dict.

        >>> d = SQLiteDict.example()
        >>> d["foo"] = CacheEntry.example()
        >>> list(iter(d)) == ["foo"]
        True
        """
        with self.Session() as db:
            for instance in db.query(Data).all():
                yield instance.key

    def __len__(self) -> int:
        """
        Returns the number of items in the cache.

        >>> d = SQLiteDict.example()
        >>> len(d)
        0
        >>> d["foo"] = CacheEntry.example()
        >>> len(d)
        1
        """
        with self.Session() as db:
            return db.query(Data).count()

    def keys(self) -> Generator[str, None, None]:
        """
        Returns a generator that yields the keys in the cache.

        >>> d = SQLiteDict.example()
        >>> d["foo"] = CacheEntry.example()
        >>> list(d.keys()) == ["foo"]
        True
        """
        return self.__iter__()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(db_path={self.db_path!r})"

    @classmethod
    def example(cls) -> SQLiteDict:
        """
        Creates an in-memory SQLiteDict for examples and testing.
        
        This factory method creates a SQLiteDict that uses an in-memory SQLite
        database, making it suitable for examples, testing, and demonstrations
        without creating persistent files.
        
        Returns:
            A new SQLiteDict instance using an in-memory SQLite database
            
        Example:
            >>> SQLiteDict.example()
            SQLiteDict(db_path='sqlite:///:memory:')
        """
        return cls(db_path="sqlite:///:memory:")


def main() -> None:
    """
    Demonstrates SQLiteDict functionality for interactive testing.
    
    This function demonstrates the key features of the SQLiteDict class,
    including creating, retrieving, updating, and deleting entries. It
    provides a practical example of how to use SQLiteDict in code.
    
    Note:
        This function is intended to be run in an interactive Python session
        for exploration and testing, not as part of normal code execution.
    """
    from .cache_entry import CacheEntry
    from .sql_dict import SQLiteDict

    # Create an in-memory SQLiteDict for demonstration
    print("Creating an in-memory SQLiteDict...")
    d = SQLiteDict.example()
    
    # Store and retrieve a value
    print("Storing and retrieving a value...")
    d["foo"] = CacheEntry.example()
    print(f"Retrieved value: {d['foo']}")
    
    # Demonstrate get() with existing and non-existing keys
    print("Demonstrating get() with existing and non-existing keys...")
    print(f"Get existing key: {d.get('foo')}")
    print(f"Get non-existing key: {d.get('poo')}")
    print(f"Get non-existing key with default: {d.get('poo', 'not found')}")
    
    # Update the dictionary
    print("Updating the dictionary...")
    d.update({"poo": CacheEntry.example()})
    print(f"After update, retrieved value: {d['poo']}")
    
    # Dictionary operations
    print("Demonstrating dictionary operations...")
    print(f"Length: {len(d)}")
    print(f"Keys: {list(d.keys())}")
    print(f"Values: {list(d.values())}")
    print(f"Items: {list(d.items())}")
    
    # Membership testing
    print("Demonstrating membership testing...")
    print(f"'poo' in d: {'poo' in d}")
    print(f"'loo' in d: {'loo' in d}")
    
    # Deletion
    print("Demonstrating deletion...")
    del d["poo"]
    print(f"After deletion, length: {len(d)}")
    
    # Representation
    print("Demonstrating string representation...")
    print(f"repr(d): {repr(d)}")
    print(f"d: {d}")


if __name__ == "__main__":
    import doctest

    doctest.testmod()

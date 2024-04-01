from __future__ import annotations
from typing import List, Optional, Generator, Union, Any

import sqlite3
import json
from edsl.data.CacheEntry import CacheEntry

class SQLiteDict:
    """A dictionary-like object that stores its data in an SQLite database."""

    EDSL_CACHE_DB_PATH = ".edsl_cache/data.db"

    def __init__(self, db_path: Optional[str] = None):
        """Construct a new SQLiteDict object.
        
        :param db_path: The path to the SQLite database file.
        """
        self.db_path = db_path or self.EDSL_CACHE_DB_PATH

        try:
            self.conn = sqlite3.connect(self.db_path)
        except sqlite3.OperationalError:
            raise Exception("Unable to connect to the database.")

        self.cursor = self.conn.cursor()
        self.cursor.execute("CREATE TABLE IF NOT EXISTS data (key TEXT PRIMARY KEY, value TEXT)")
        self.conn.commit()
        
    def __setitem__(self, key: str, value: CacheEntry) -> None:
        """Set the value at the given key.
        
        :param key: The key to set.
        :param value: The value to set.
        """
        value_json = json.dumps(value.to_dict())
        self.cursor.execute("INSERT OR REPLACE INTO data (key, value) VALUES (?, ?)", (key, value_json))
        self.conn.commit()
        
    def __getitem__(self, key: str) -> CacheEntry:
        """Get the value at the given key.

        :param key: The key to get.

        >>> d = SQLiteDict.example()
        >>> d["foo"] = CacheEntry.example()
        >>> d["foo"] == CacheEntry.example()
        True
        """
        self.cursor.execute("SELECT value FROM data WHERE key = ?", (key,))
        result = self.cursor.fetchone()
        if result:
            return CacheEntry.from_dict(json.loads(result[0]))
        raise KeyError(f"Key '{key}' not found.")
    
    def get(self, key: str, default=None) -> Union[CacheEntry, Any]:
        """Get the value at the given key, or a default value if the key is not found.
        
        :param key: The key to use to get the value.
        :param default: The default value to return if the key is not found.

        >>> d = SQLiteDict.example()
        >>> d.get("foo", "bar")
        'bar'
        """
        try:
            return self[key]
        except KeyError:
            return default
        
    def update(self, new_d: dict, overwrite:bool = False) -> None:
        """Update the dictionary with the values from another dictionary.
        
        :param new_d: The dictionary to update with.
        :param overwrite: Whether to overwrite existing values.

        >>> d = SQLiteDict.example()
        >>> d.update({"foo": CacheEntry.example()})
        """
        for key, value in new_d.items():
            if key in self:
                if overwrite:
                    self[key] = value
            else:
                self[key] = value    

    def values(self) -> Generator[CacheEntry, None, None]:
        """Return a generator that yields the values in the cache.
        
        >>> d = SQLiteDict.example()
        >>> d["foo"] = CacheEntry.example()
        >>> list(d.values()) == [CacheEntry.example()]
        True
        """
        self.cursor.execute("SELECT value from data")
        for value in self.cursor.fetchall():
            yield CacheEntry(**json.loads(value[0]))

    def items(self) -> Generator[tuple[str, CacheEntry], None, None]:
        """Return a generator that yields the items in the cache.
        
        >>> d = SQLiteDict.example()
        >>> d["foo"] = CacheEntry.example()
        >>> list(d.items()) == [("foo", CacheEntry.example())]
        True
        """
        self.cursor.execute("SELECT key, value FROM data")
        for key, value in self.cursor.fetchall():
            yield key, CacheEntry(**json.loads(value))
        
    def __delitem__(self, key) -> None:
        """Delete the value at the given key.
        
        :param key: The key to delete.

        >>> d = SQLiteDict.example()
        >>> d["foo"] = CacheEntry.example()
        >>> del d["foo"]
        >>> d.get("foo", "missing")
        'missing'
        """
        if key in self:
            self.cursor.execute("DELETE FROM data WHERE key = ?", (key,))
            self.conn.commit()
        else:
            raise KeyError(f"Key '{key}' not found.")
            
    def __contains__(self, key: str) -> bool:
        """Check if the cache contains the given key.
        
        :param key: The key to check for.

        >>> d = SQLiteDict.example()
        >>> d["foo"] = CacheEntry.example()
        >>> "foo" in d
        True
        >>> "bar" in d
        False
        """
        self.cursor.execute("SELECT 1 FROM data WHERE key = ?", (key,))
        return self.cursor.fetchone() is not None
    
    def __iter__(self) -> Generator[str, None, None]:
        """Return a generator that yields the keys in the cache.
        
        >>> d = SQLiteDict.example()
        >>> d["foo"] = CacheEntry.example()
        >>> list(iter(d)) == ["foo"]
        True
        """
        self.cursor.execute("SELECT key FROM data")
        for row in self.cursor.fetchall():
            yield row[0]
            
    def __len__(self) -> int:
        """Return the number of items in the cache.
        
        >>> d = SQLiteDict.example()
        >>> len(d)
        0
        >>> d["foo"] = CacheEntry.example()
        >>> len(d)
        1
        """
        self.cursor.execute("SELECT COUNT(*) FROM data")
        return self.cursor.fetchone()[0]
    
    def keys(self) -> Generator[str, None, None]:
        """Return a generator that yields the keys in the cache.
        
        >>> d = SQLiteDict.example()
        >>> d["foo"] = CacheEntry.example()
        >>> list(d.keys()) == ["foo"]
        True
        """
        self.cursor.execute("SELECT key from data")
        for row in self.cursor.fetchall():
            yield row[0]
    
    def close(self) -> None:
        """Close the connection to the database."""
        self.conn.close()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(db_path={self.db_path!r})"

    @classmethod
    def example(cls) -> SQLiteDict:
        """Return an example SQLiteDict object.
        
        >>> SQLiteDict.example()
        SQLiteDict(db_path=':memory:')
        """
        return cls(db_path=":memory:")

if __name__ == "__main__":
    import doctest
    doctest.testmod()
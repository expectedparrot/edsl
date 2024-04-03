from __future__ import annotations
import json
import sqlite3
from typing import Any, Generator, Optional, Union
from edsl.config import CONFIG
from edsl.data.CacheEntry import CacheEntry


class SQLiteDict:
    """
    A dictionary-like object that is an interface for an SQLite database.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path or CONFIG.get("EDSL_DATABASE_PATH")
        try:
            self.conn = sqlite3.connect(self.db_path)
        except sqlite3.OperationalError:
            raise Exception(f"Unable to connect to the database ({self.db_path}).")
        self.cursor = self.conn.cursor()
        self.cursor.execute(
            "CREATE TABLE IF NOT EXISTS data (key TEXT PRIMARY KEY, value TEXT)"
        )
        self.conn.commit()

    def __setitem__(self, key: str, value: CacheEntry) -> None:
        """
        Stores a key-value pair.

        >>> d = SQLiteDict.example()
        >>> d["foo"] = CacheEntry.example()
        """
        if not isinstance(value, CacheEntry):
            raise ValueError(f"Value must be a CacheEntry object (got {type(value)}.")
        self.cursor.execute(
            "INSERT OR REPLACE INTO data (key, value) VALUES (?, ?)",
            (key, json.dumps(value.to_dict())),
        )
        self.conn.commit()

    def __getitem__(self, key: str) -> CacheEntry:
        """
        Gets a value for a given key.
        - Raises a KeyError if the key is not found.

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

    def get(self, key: str, default: Optional[Any] = None) -> Union[CacheEntry, Any]:
        """
        Gets the value for a given key
        - Returns the `default` value if the key is not found.

        >>> d = SQLiteDict.example()
        >>> d.get("foo", "bar")
        'bar'
        """
        try:
            return self[key]
        except KeyError:
            return default

    def update(
        self, new_d: Union[dict, SQLiteDict], overwrite: Optional[bool] = False
    ) -> None:
        """
        Updates the dictionary with the values from another dictionary.
        - If `overwrite` is True, existing values will be overwritten.

        >>> d = SQLiteDict.example()
        >>> d.update({"foo": CacheEntry.example()})
        >>> d["foo"] == CacheEntry.example()
        True
        """
        if not (isinstance(new_d, dict) or isinstance(new_d, SQLiteDict)):
            raise ValueError(
                f"new_d must be a dict or SQLiteDict object (got {type(new_d)})"
            )
        for key, value in new_d.items():
            if key in self and overwrite:
                self[key] = value
            else:
                self[key] = value

    def values(self) -> Generator[CacheEntry, None, None]:
        """
        Returns a generator that yields the values in the cache.

        >>> d = SQLiteDict.example()
        >>> d["foo"] = CacheEntry.example()
        >>> list(d.values()) == [CacheEntry.example()]
        True
        """
        self.cursor.execute("SELECT value from data")
        for value in self.cursor.fetchall():
            yield CacheEntry(**json.loads(value[0]))

    def items(self) -> Generator[tuple[str, CacheEntry], None, None]:
        """
        Returns a generator that yields the items in the cache.

        >>> d = SQLiteDict.example()
        >>> d["foo"] = CacheEntry.example()
        >>> list(d.items()) == [("foo", CacheEntry.example())]
        True
        """
        self.cursor.execute("SELECT key, value FROM data")
        for key, value in self.cursor.fetchall():
            yield key, CacheEntry(**json.loads(value))

    def __delitem__(self, key: str) -> None:
        """
        Deletes the value for a given key.

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
        """
        Checks if the dict contains the given key.

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
        """
        Returns a generator that yields the keys in the dict.

        >>> d = SQLiteDict.example()
        >>> d["foo"] = CacheEntry.example()
        >>> list(iter(d)) == ["foo"]
        True
        """
        self.cursor.execute("SELECT key FROM data")
        for row in self.cursor.fetchall():
            yield row[0]

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
        self.cursor.execute("SELECT COUNT(*) FROM data")
        return self.cursor.fetchone()[0]

    def keys(self) -> Generator[str, None, None]:
        """
        Returns a generator that yields the keys in the cache.

        >>> d = SQLiteDict.example()
        >>> d["foo"] = CacheEntry.example()
        >>> list(d.keys()) == ["foo"]
        True
        """
        self.cursor.execute("SELECT key from data")
        for row in self.cursor.fetchall():
            yield row[0]

    def close(self) -> None:
        """
        Closes the database connection.
        """
        self.conn.close()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(db_path={self.db_path!r})"

    @classmethod
    def example(cls) -> SQLiteDict:
        """
        Returns an example SQLiteDict object.
        - The example SQLiteDict is empty and stored in memory.

        >>> SQLiteDict.example()
        SQLiteDict(db_path=':memory:')
        """
        return cls(db_path=":memory:")


if __name__ == "__main__":
    import doctest

    doctest.testmod()

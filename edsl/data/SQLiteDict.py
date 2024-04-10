from __future__ import annotations
import json
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker
from typing import Any, Generator, Optional, Union
from edsl.config import CONFIG
from edsl.data.CacheEntry import CacheEntry
from edsl.data.orm import Base, Data


class SQLiteDict:
    """
    A dictionary-like object that is an interface for an local database.
    - You can use SQLiteDict as a regular dictionary.
    - Supports only SQLite for now.
    """

    def __init__(self, db_path: Optional[str] = None):
        """

        >>> temp_db_path = self._get_temp_path()
        >>> SQLiteDict(f"sqlite:///{temp_db_path}")  # Use the temp file for SQLite
        >>> os.unlink(temp_db_path)  # Clean up the temp file after the test

        """
        self.db_path = db_path or CONFIG.get("EDSL_DATABASE_PATH")
        if not self.db_path.startswith("sqlite:///"):
            self.db_path = f"sqlite:///{self.db_path}"
        try:
            self.engine = create_engine(self.db_path, echo=False, future=True)
            Base.metadata.create_all(self.engine)
            self.Session = sessionmaker(bind=self.engine)
        except SQLAlchemyError as e:
            raise Exception(
                f"""Database initialization error: {e}. The attempted DB path was {db_path}"""
            ) from e

    def _get_temp_path(self):
        import tempfile
        import os

        _, temp_db_path = tempfile.mkstemp(suffix=".db")
        return temp_db_path

    def __setitem__(self, key: str, value: CacheEntry) -> None:
        """
        Stores a key-value pair.

        >>> d = SQLiteDict.example()
        >>> d["foo"] = CacheEntry.example()
        """
        if not isinstance(value, CacheEntry):
            raise ValueError(f"Value must be a CacheEntry object (got {type(value)}).")
        with self.Session() as db:
            db.merge(Data(key=key, value=json.dumps(value.to_dict())))
            db.commit()

    def __getitem__(self, key: str) -> CacheEntry:
        """
        Gets a value for a given key.
        - Raises a KeyError if the key is not found.

        >>> d = SQLiteDict.example()
        >>> d["foo"] = CacheEntry.example()
        >>> d["foo"] == CacheEntry.example()
        True
        """
        with self.Session() as db:
            value = db.query(Data).filter_by(key=key).first()
            if not value:
                raise KeyError(f"Key '{key}' not found.")
            return CacheEntry.from_dict(json.loads(value.value))

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

    def __bool__(self) -> bool:
        """This is so likes like
        self.data = data or {} 'work' as expected
        """
        return True

    def update(
        self,
        new_d: Union[dict, SQLiteDict],
        overwrite: Optional[bool] = False,
        max_batch_size: Optional[int] = 100,
    ) -> None:
        """
        Update the dictionary with the values from another dictionary.

        :param new_d: The dictionary to update the current dictionary with.
        :param overwrite: If `overwrite` is False, existing values will not be overwritten.
        :param max_batch_size: The maximum number of items to update in a single transaction.

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
        current_batch = 0
        with self.Session() as db:
            for key, value in new_d.items():
                if current_batch == max_batch_size:
                    db.commit()
                    current_batch = 0
                current_batch += 1
                if key in self:
                    if overwrite:
                        db.merge(Data(key=key, value=json.dumps(value.to_dict())))
                else:
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
        Returns an example SQLiteDict object.
        - The example SQLiteDict is empty and stored in memory.

        >>> SQLiteDict.example()
        SQLiteDict(db_path='sqlite:///:memory:')
        """
        return cls(db_path="sqlite:///:memory:")


def main():
    from edsl.data.CacheEntry import CacheEntry
    from edsl.data.SQLiteDict import SQLiteDict

    d = SQLiteDict.example()
    d["foo"] = CacheEntry.example()
    d["foo"]
    d.get("foo")
    d.get("poo")
    d.get("poo", "not found")
    d.update({"poo": CacheEntry.example()})
    d["poo"]
    len(d)
    list(d.keys())
    list(d.values())
    list(d.items())
    assert "poo" in d
    assert "loo" not in d
    del d["poo"]
    assert len(d) == 1
    repr(d)
    d


if __name__ == "__main__":
    import doctest

    doctest.testmod()

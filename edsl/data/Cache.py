"""
The `Cache` class is used to store responses from a language model.
"""

from __future__ import annotations
import json
import os
import warnings
from typing import Optional, Union
from edsl.Base import Base
from edsl.data.CacheEntry import CacheEntry
from edsl.utilities.utilities import dict_hash
from edsl.utilities.decorators import add_edsl_version, remove_edsl_version


class Cache(Base):
    """
    A class that represents a cache of responses from a language model.

    :param data: The data to initialize the cache with.
    :param immediate_write: Whether to write to the cache immediately after storing a new entry.

    Deprecated:

    :param method: The method of storage to use for the cache.
    """

    data = {}

    def __init__(
        self,
        *,
        filename: Optional[str] = None,
        data: Optional[Union["SQLiteDict", dict]] = None,
        immediate_write: bool = True,
        method=None,
        verbose=False,
    ):
        """
        Create two dictionaries to store the cache data.

        :param filename: The name of the file to read/write the cache from/to.
        :param data: The data to initialize the cache with.
        :param immediate_write: Whether to write to the cache immediately after storing a new entry.
        :param method: The method of storage to use for the cache.

        """

        # self.data_at_init = data or {}
        self.fetched_data = {}
        self.immediate_write = immediate_write
        self.method = method
        self.new_entries = {}
        self.new_entries_to_write_later = {}
        self.coop = None
        self.verbose = verbose

        self.filename = filename
        if filename and data:
            raise ValueError("Cannot provide both filename and data")
        if filename is None and data is None:
            data = {}
        if data is not None:
            self.data = data
        if filename is not None:
            self.data = {}
            if filename.endswith(".jsonl"):
                if os.path.exists(filename):
                    self.add_from_jsonl(filename)
                else:
                    print(
                        f"File {filename} not found, but will write to this location."
                    )
            elif filename.endswith(".db"):
                if os.path.exists(filename):
                    self.add_from_sqlite(filename)
            else:
                raise ValueError("Invalid file extension. Must be .jsonl or .db")

        self._perform_checks()

    def rich_print(sefl):
        pass
        # raise NotImplementedError("This method is not implemented yet.")

    def code(sefl):
        pass
        # raise NotImplementedError("This method is not implemented yet.")

    def keys(self):
        return list(self.data.keys())

    def values(self):
        return list(self.data.values())

    def new_entries_cache(self) -> Cache:
        """Return a new Cache object with the new entries."""
        return Cache(data={**self.new_entries, **self.fetched_data})

    def _perform_checks(self):
        """Perform checks on the cache."""
        from edsl.data.CacheEntry import CacheEntry

        if any(not isinstance(value, CacheEntry) for value in self.data.values()):
            raise Exception("Not all values are CacheEntry instances")
        if self.method is not None:
            warnings.warn("Argument `method` is deprecated", DeprecationWarning)

    ####################
    # READ/WRITE
    ####################
    def fetch(
        self,
        *,
        model: str,
        parameters: dict,
        system_prompt: str,
        user_prompt: str,
        iteration: int,
    ) -> tuple(Union[None, str], str):
        """
        Fetch a value (LLM output) from the cache.

        :param model: The name of the language model.
        :param parameters: The model parameters.
        :param system_prompt: The system prompt.
        :param user_prompt: The user prompt.
        :param iteration: The iteration number.

        Return None if the response is not found.

        >>> c = Cache()
        >>> c.fetch(model="gpt-3", parameters="default", system_prompt="Hello", user_prompt="Hi", iteration=1)[0] is None
        True


        """
        from edsl.data.CacheEntry import CacheEntry

        key = CacheEntry.gen_key(
            model=model,
            parameters=parameters,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            iteration=iteration,
        )
        entry = self.data.get(key, None)
        if entry is not None:
            if self.verbose:
                print(f"Cache hit for key: {key}")
            self.fetched_data[key] = entry
        else:
            if self.verbose:
                print(f"Cache miss for key: {key}")
        return None if entry is None else entry.output, key

    def store(
        self,
        model: str,
        parameters: str,
        system_prompt: str,
        user_prompt: str,
        response: str,
        iteration: int,
    ) -> str:
        """
        Add a new key-value pair to the cache.

        * Key is a hash of the input parameters.
        * Output is the response from the language model.

        How it works:

        * The key-value pair is added to `self.new_entries`
        * If `immediate_write` is True , the key-value pair is added to `self.data`
        * If `immediate_write` is False, the key-value pair is added to `self.new_entries_to_write_later`
        """

        entry = CacheEntry(
            model=model,
            parameters=parameters,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output=json.dumps(response),
            iteration=iteration,
        )
        key = entry.key
        self.new_entries[key] = entry
        if self.immediate_write:
            self.data[key] = entry
        else:
            self.new_entries_to_write_later[key] = entry
        return key

    def add_from_dict(
        self, new_data: dict[str, "CacheEntry"], write_now: Optional[bool] = True
    ) -> None:
        """
        Add entries to the cache from a dictionary.

        :param write_now: Whether to write to the cache immediately (similar to `immediate_write`).
        """

        for key, value in new_data.items():
            if key in self.data:
                if value != self.data[key]:
                    raise Exception("Mismatch in values")
            if not isinstance(value, CacheEntry):
                raise Exception(f"Wrong type - the observed type is {type(value)}")

        self.new_entries.update(new_data)
        if write_now:
            self.data.update(new_data)
        else:
            self.new_entries_to_write_later.update(new_data)

    def add_from_jsonl(self, filename: str, write_now: Optional[bool] = True) -> None:
        """
        Add entries to the cache from a JSONL.

        :param write_now: Whether to write to the cache immediately (similar to `immediate_write`).
        """
        with open(filename, "a+") as f:
            f.seek(0)
            lines = f.readlines()
        new_data = {}
        for line in lines:
            d = json.loads(line)
            key = list(d.keys())[0]
            value = list(d.values())[0]
            new_data[key] = CacheEntry(**value)
        self.add_from_dict(new_data=new_data, write_now=write_now)

    def add_from_sqlite(self, db_path: str, write_now: Optional[bool] = True):
        """
        Add entries to the cache from an SQLite database.

        :param write_now: Whether to write to the cache immediately (similar to `immediate_write`).
        """
        from edsl.data.SQLiteDict import SQLiteDict

        db = SQLiteDict(db_path)
        new_data = {}
        for key, value in db.items():
            new_data[key] = CacheEntry(**value)
        self.add_from_dict(new_data=new_data, write_now=write_now)

    @classmethod
    def from_sqlite_db(cls, db_path: str) -> Cache:
        """
        Construct a Cache from a SQLite database.
        """
        from edsl.data.SQLiteDict import SQLiteDict

        return cls(data=SQLiteDict(db_path))

    @classmethod
    def from_local_cache(cls) -> Cache:
        """
        Construct a Cache from a local cache file.
        """
        from edsl.config import CONFIG

        CACHE_PATH = CONFIG.get("EDSL_DATABASE_PATH")
        path = CACHE_PATH.replace("sqlite:///", "")
        db_path = os.path.join(os.path.dirname(path), "data.db")
        return cls.from_sqlite_db(db_path=db_path)

    @classmethod
    def from_jsonl(cls, jsonlfile: str, db_path: Optional[str] = None) -> Cache:
        """
        Construct a Cache from a JSONL file.

        :param jsonlfile: The path to the JSONL file of cache entries.
        :param db_path: The path to the SQLite database used to store the cache.

        * If `db_path` is None, the cache will be stored in memory, as a dictionary.
        * If `db_path` is provided, the cache will be stored in an SQLite database.
        """
        # if a file doesn't exist at jsonfile, throw an error
        from edsl.data.SQLiteDict import SQLiteDict

        if not os.path.exists(jsonlfile):
            raise FileNotFoundError(f"File {jsonlfile} not found")

        if db_path is None:
            data = {}
        else:
            data = SQLiteDict(db_path)

        cache = Cache(data=data)
        cache.add_from_jsonl(jsonlfile)
        return cache

    def write_sqlite_db(self, db_path: str) -> None:
        """
        Write the cache to an SQLite database.
        """
        ## TODO: Check to make sure not over-writing (?)
        ## Should be added to SQLiteDict constructor (?)
        from edsl.data.SQLiteDict import SQLiteDict

        new_data = SQLiteDict(db_path)
        for key, value in self.data.items():
            new_data[key] = value

    def write(self, filename: Optional[str] = None) -> None:
        """
        Write the cache to a file at the specified location.
        """
        if filename is None:
            filename = self.filename
        if filename.endswith(".jsonl"):
            self.write_jsonl(filename)
        elif filename.endswith(".db"):
            self.write_sqlite_db(filename)
        else:
            raise ValueError("Invalid file extension. Must be .jsonl or .db")

    def write_jsonl(self, filename: str) -> None:
        """
        Write the cache to a JSONL file.
        """
        path = os.path.join(os.getcwd(), filename)
        with open(path, "w") as f:
            for key, value in self.data.items():
                f.write(json.dumps({key: value.to_dict()}) + "\n")

    ####################
    # REMOTE
    ####################
    # TODO: Make this work
    # - Need to decide whether the cache belongs to a user and what can be shared
    # - I.e., some cache entries? all or nothing?
    @classmethod
    def from_url(cls, db_path=None) -> Cache:
        """
        Construct a Cache object from a remote.
        """
        # ...do something here
        # return Cache(data=db)
        pass

    def __enter__(self):
        """
        Run when a context is entered.
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Run when a context is exited.
        """
        for key, entry in self.new_entries_to_write_later.items():
            self.data[key] = entry

        if self.filename:
            self.write(self.filename)

    ####################
    # DUNDER / USEFUL
    ####################
    def __hash__(self):
        """Return the hash of the Cache."""
        return dict_hash(self._to_dict())

    def _to_dict(self) -> dict:
        return {k: v.to_dict() for k, v in self.data.items()}

    @add_edsl_version
    def to_dict(self) -> dict:
        """Return the Cache as a dictionary."""
        return self._to_dict()

    def _repr_html_(self):
        from edsl.utilities.utilities import data_to_html

        return data_to_html(self.to_dict())

    @classmethod
    @remove_edsl_version
    def from_dict(cls, data) -> Cache:
        """Construct a Cache from a dictionary."""
        newdata = {k: CacheEntry.from_dict(v) for k, v in data.items()}
        return cls(data=newdata)

    def __len__(self):
        """Return the number of CacheEntry objects in the Cache."""
        return len(self.data)

    # TODO: Same inputs could give different results and this could be useful
    # can't distinguish unless we do the ε trick or vary iterations
    def __eq__(self, other_cache: "Cache") -> bool:
        """
        Check if two Cache objects are equal.
        Does not verify their values are equal, only that they have the same keys.
        """
        if not isinstance(other_cache, Cache):
            return False
        return set(self.data.keys()) == set(other_cache.data.keys())

    def __add__(self, other: "Cache"):
        """
        Combine two caches.
        """
        if not isinstance(other, Cache):
            raise ValueError("Can only add two caches together")
        self.data.update(other.data)
        return self

    def __repr__(self):
        """
        Return a string representation of the Cache object.
        """
        return (
            f"Cache(data = {repr(self.data)}, immediate_write={self.immediate_write})"
        )

    ####################
    # EXAMPLES
    ####################
    def fetch_input_example(self) -> dict:
        """
        Create an example input for a 'fetch' operation.
        """
        return CacheEntry.fetch_input_example()

    def to_html(self):
        # json_str = json.dumps(self.data, indent=4)
        d = {k: v.to_dict() for k, v in self.data.items()}
        for key, value in d.items():
            for k, v in value.items():
                if isinstance(v, dict):
                    d[key][k] = {kk: str(vv) for kk, vv in v.items()}
                else:
                    d[key][k] = str(v)

        json_str = json.dumps(d, indent=4)

        # HTML template with the JSON string embedded
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Display JSON</title>
        </head>
        <body>
            <pre id="jsonData"></pre>
            <script>
                var json = {json_str};

                // JSON.stringify with spacing to format
                document.getElementById('jsonData').textContent = JSON.stringify(json, null, 4);
            </script>
        </body>
        </html>
        """
        return html

    def view(self) -> None:
        """View the Cache in a new browser tab."""
        import tempfile
        import webbrowser

        html_content = self.to_html()
        # Create a temporary file to hold the HTML
        with tempfile.NamedTemporaryFile("w", delete=False, suffix=".html") as tmpfile:
            tmpfile.write(html_content)
            # Get the path to the temporary file
            filepath = tmpfile.name

        # Open the HTML file in a new browser tab
        webbrowser.open("file://" + filepath)

    @classmethod
    def example(cls, randomize: bool = False) -> Cache:
        """
        Returns an example Cache instance.

        :param randomize: If True, uses CacheEntry's randomize method.
        """
        return cls(
            data={
                CacheEntry.example(randomize).key: CacheEntry.example(),
                CacheEntry.example(randomize).key: CacheEntry.example(),
            }
        )


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)

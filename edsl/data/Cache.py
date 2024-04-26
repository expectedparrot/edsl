from __future__ import annotations
import json
import os
import warnings
from typing import Optional, Union
from edsl.config import CONFIG
from edsl.data.CacheEntry import CacheEntry
from edsl.data.SQLiteDict import SQLiteDict


# EDSL_DATABASE_PATH = CONFIG.get("EDSL_DATABASE_PATH")
# EXPECTED_PARROT_CACHE_URL = os.getenv("EXPECTED_PARROT_CACHE_URL")

# TODO: What do we want to do if & when there is a mismatch
#       -- if two keys are the same but the values are different?
# TODO: In the read methods, if the file already exists, make sure it is valid.


class Cache:
    """
    A class that represents a cache of responses from a language model.

    :param data: The data to initialize the cache with.
    :param remote: Whether to sync the Cache with the server.
    :param immediate_write: Whether to write to the cache immediately after storing a new entry.

    Deprecated:

    :param method: The method of storage to use for the cache.
    """

    data = {}

    def __init__(
        self,
        *,
        data: Optional[Union[SQLiteDict, dict]] = None,
        remote: bool = False,
        immediate_write: bool = True,
        method=None,
    ):
        """
        Create two dictionaries to store the cache data.

        :param new_entries: Entries that are created during a __enter__ block.
        :param new_entries_to_write_later: Entries that will be written to the cache later.
        """
        self.data = data or {}
        self.remote = remote
        self.immediate_write = immediate_write
        self.method = method
        self.new_entries = {}
        self.new_entries_to_write_later = {}
        self.coop = None
        self._perform_checks()

    def keys(self):
        return list(self.data.keys())

    def values(self):
        return list(self.data.values())

    def _perform_checks(self):
        """Perform checks on the cache."""
        if any(not isinstance(value, CacheEntry) for value in self.data.values()):
            raise Exception("Not all values are CacheEntry instances")
        if self.method is not None:
            warnings.warn("Argument `method` is deprecated", DeprecationWarning)
        if self.remote:
            from edsl.coop import Coop

            self.coop = Coop()

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
    ) -> Union[None, str]:
        """
        Fetch a value (LLM output) from the cache.
        Return None if the response is not found.
        """
        key = CacheEntry.gen_key(
            model=model,
            parameters=parameters,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            iteration=iteration,
        )
        entry = self.data.get(key, None)
        return None if entry is None else entry.output

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
        self, new_data: dict[str, CacheEntry], write_now: Optional[bool] = True
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
        return cls(data=SQLiteDict(db_path))

    @classmethod
    def from_jsonl(cls, jsonlfile: str, db_path: str = None) -> Cache:
        """
        Construct a Cache from a JSONL file.

        * If `db_path` is None, the cache will be stored in memory, as a dictionary.
        * If `db_path` is provided, the cache will be stored in an SQLite database.
        """
        if db_path is None:
            data = {}
        else:
            data = SQLiteDict(db_path)

        # if a file doesn't exist at jsonfile, throw an error
        if not os.path.exists(jsonlfile):
            raise FileNotFoundError(f"File {jsonlfile} not found")

        cache = Cache(data=data)
        cache.add_from_jsonl(jsonlfile)
        return cache

    ## TODO: Check to make sure not over-writing (?)
    ## Should be added to SQLiteDict constructor (?)
    def write_sqlite_db(self, db_path: str) -> None:
        """
        Write the cache to an SQLite database.
        """
        new_data = SQLiteDict(db_path)
        for key, value in self.data.items():
            new_data[key] = value

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
        if self.remote:
            print("Syncing local and remote caches")
            exclude_keys = list(self.data.keys())
            cache_entries = self.coop.get_cache_entries(exclude_keys)
            self.add_from_dict({c.key: c for c in cache_entries}, write_now=True)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Run when a context is exited.
        """
        for key, entry in self.new_entries_to_write_later.items():
            self.data[key] = entry
        if self.remote:
            _ = self.coop.send_cache_entries(cache_dict=self.new_entries)

    ####################
    # DUNDER / USEFUL
    ####################
    def to_dict(self) -> dict:
        """Return the Cache as a dictionary."""
        return {k: v.to_dict() for k, v in self.data.items()}

    def _repr_html_(self):
        from edsl.utilities.utilities import data_to_html

        return data_to_html(self.to_dict())

    @classmethod
    def from_dict(cls, data) -> Cache:
        """Construct a Cache from a dictionary."""
        data = {k: CacheEntry.from_dict(v) for k, v in data}
        return cls(data=data)

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
        return f"Cache(data = {repr(self.data)}, immediate_write={self.immediate_write}, remote={self.remote})"

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
    def example(cls) -> Cache:
        """
        Return an example Cache.
        The example Cache has one entry.
        """
        return cls(data={CacheEntry.example().key: CacheEntry.example()})


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)

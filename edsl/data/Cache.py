from __future__ import annotations
import json
import os
import warnings
from typing import Optional, Union
from edsl.config import CONFIG
from edsl.data.CacheEntry import CacheEntry
from edsl.data.SQLiteDict import SQLiteDict


EDSL_DATABASE_PATH = CONFIG.get("EDSL_DATABASE_PATH")
EXPECTED_PARROT_CACHE_URL = os.getenv("EXPECTED_PARROT_CACHE_URL")

# TODO: What do we want to do if & when there is a mismatch
#       -- if two keys are the same but the values are different?
# TODO: In the read methods, if the file already exists, make sure it is valid.


class Cache:
    """
    A class that represents a cache of responses from a language model.

    - `data`: The data to initialize the cache with.
    - `remote`: Whether to sync the Cache with the server.
    - `immediate_write`: Whether to write to the cache immediately after storing a new entry.

    Deprecated:
    - `method`: the method of storage to use for the cache.
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
        Creates two dictionaries to store the cache data.
        - `new_entries`: entries that are created during a __enter__ block
        - `new_entries_to_write_later`: entries that will be written to the cache later
        """
        self.data = data or {}
        self.remote = remote
        self.immediate_write = immediate_write
        self.method = method
        self.new_entries = {}
        self.new_entries_to_write_later = {}
        self.coop = None
        self._perform_checks()

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
        Fetches a value (LLM output) from the cache.
        - Returns None if the response is not found.
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
        Adds a new key-value pair to the cache.
        - Key is a hash of the input parameters.
        - Output is the response from the language model.

        How it works
        - The key-value pair is added to `self.new_entries`
        - If `immediate_write` is True , the key-value pair is added to `self.data`
        - If `immediate_write` is False, the key-value pair is added to `self.new_entries_to_write_later`
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
        - `write_now` whether to write to the cache immediately (similar to `immediate_write`).
        """
        for key, value in new_data.items():
            if key in self.data:
                if value != self.data[key]:
                    raise Exception("Mismatch in values")
            if not isinstance(value, CacheEntry):
                raise Exception("Wrong type")

        self.new_entries.update(new_data)
        if write_now:
            self.data.update(new_data)
        else:
            self.new_entries_to_write_later.update(new_data)

    def add_from_jsonl(self, filename: str, write_now: Optional[bool] = True) -> None:
        """
        Add entries to the cache from a JSONL.
        - `write_now` whether to write to the cache immediately (similar to `immediate_write`).
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
        - `write_now` whether to write to the cache immediately (similar to `immediate_write`).
        """
        db = SQLiteDict(db_path)
        new_data = {}
        for key, value in db.items():
            new_data[key] = CacheEntry(**value)
        self.add_from_dict(new_data=new_data, write_now=write_now)

    @classmethod
    def from_sqlite_db(cls, db_path: str) -> Cache:
        """
        Construct a Cache from an SQLite database.
        """
        return cls(data=SQLiteDict(db_path))

    @classmethod
    def from_jsonl(cls, jsonlfile: str, db_path: str = None) -> Cache:
        """
        Construct a Cache from a JSONL file.
        - if `db_path` is None, the cache will be stored in memory, as a dictionary.
        - if `db_path` is provided, the cache will be stored in an SQLite database.
        """
        if db_path is None:
            data = {}
        else:
            data = SQLiteDict(db_path)
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
        Runs when a context is entered.
        """
        if self.remote:
            print("Syncing local and remote caches")
            exclude_keys = list(self.data.keys())
            cache_entries = self.coop.get_cache_entries(exclude_keys)
            self.add_from_dict({c.key: c for c in cache_entries}, write_now=True)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Runs when a context is exited.
        """
        for key, entry in self.new_entries_to_write_later.items():
            self.data[key] = entry
        if self.remote:
            _ = self.coop.send_cache_entries(cache_dict=self.new_entries)

    ####################
    # DUNDER / USEFUL
    ####################
    def to_dict(self) -> dict:
        return {k: v.to_dict() for k, v in self.data.items()}

    @classmethod
    def from_dict(cls, data) -> Cache:
        data = {k: CacheEntry.from_dict(v) for k, v in data}
        return cls(data=data)

    def __len__(self):
        """Returns the number of CacheEntry objects in the Cache."""
        return len(self.data)

    # TODO: Same inputs could give different results and this could be useful
    # can't distinguish unless we do the ε trick or vary iterations
    def __eq__(self, other_cache: "Cache") -> bool:
        """
        Checks if two Cache objects are equal.
        - Doesn't verify their values are equal, just that they have the same keys.
        """
        if not isinstance(other_cache, Cache):
            return False
        return set(self.data.keys()) == set(other_cache.data.keys())

    def __add__(self, other: "Cache"):
        """
        Combines two caches.
        """
        if not isinstance(other, Cache):
            raise ValueError("Can only add two caches together")
        self.data.update(other.data)
        return self

    def __repr__(self):
        """
        Returns a string representation of the Cache object.
        """
        return f"Cache(data = {repr(self.data)}, immediate_write={self.immediate_write}, remote={self.remote})"

    ####################
    # EXAMPLES
    ####################
    def fetch_input_example(self) -> dict:
        """
        Creates an example input for a 'fetch' operation.
        """
        return CacheEntry.fetch_input_example()

    @classmethod
    def example(cls) -> Cache:
        """
        Return an example Cache.
        - The example Cache has one entry.
        """
        return cls(data={CacheEntry.example().key: CacheEntry.example()})


def main():
    import os
    from edsl.data.CacheEntry import CacheEntry
    from edsl.data.Cache import Cache

    # fetch
    cache = Cache()
    assert (
        cache.fetch(
            model="gpt-3.5-turbo",
            parameters="{'temperature': 0.5}",
            system_prompt="The quick brown fox jumps over the lazy dog.",
            user_prompt="What does the fox say?",
            iteration=1,
        )
        == None
    )
    cache = Cache.example()
    assert cache.fetch(**cache.fetch_input_example()) == "The fox says 'hello'"

    # store with immediate write
    cache = Cache()
    input = CacheEntry.store_input_example()
    cache.store(**input)
    assert list(cache.data.keys()) == ["5513286eb6967abc0511211f0402587d"]

    # store with delayed write
    cache = Cache(immediate_write=False)
    input = CacheEntry.store_input_example()
    cache.store(**input)
    assert list(cache.data.keys()) == []

    # use context manager to write delayed entries
    cache = Cache(immediate_write=False)
    cache = cache.__enter__()
    input = CacheEntry.store_input_example()
    cache.store(**input)
    assert list(cache.data.keys()) == []
    cache.__exit__(None, None, None)
    assert list(cache.data.keys()) == ["5513286eb6967abc0511211f0402587d"]

    # add multiple entries from a dict with immediate write
    cache = Cache()
    data = {"poo": CacheEntry.example(), "bandits": CacheEntry.example()}
    cache.add_from_dict(new_data=data)
    assert cache.data["poo"] == CacheEntry.example()
    # with delayed write
    cache = Cache()
    data = {"poo": CacheEntry.example(), "bandits": CacheEntry.example()}
    cache.add_from_dict(new_data=data, write_now=False)
    assert cache.data == {}
    cache.__exit__(None, None, None)
    assert cache.data["poo"] == CacheEntry.example()

    # add multiple entries from a JSONL file with immediate write
    cache = Cache(data=CacheEntry.example_dict())
    cache.write_jsonl("example.jsonl")
    cache_new = Cache()
    cache_new.add_from_jsonl(filename="example.jsonl")
    assert cache == cache_new
    os.remove("example.jsonl")

    # add multiple entries from a SQLite db with immediate write
    cache = Cache.example()
    cache.data["poo"] = CacheEntry.example()
    cache.write_sqlite_db("sqlite:///example.db")
    cache_new = Cache.from_sqlite_db("sqlite:///example.db")
    assert cache == cache_new
    os.remove("example.db")

    # construct a cache from a jsonl file and save to memory
    cache = Cache.example()
    cache.write_jsonl("example.jsonl")
    cache_new = Cache.from_jsonl("example.jsonl")
    assert cache == cache_new
    os.remove("example.jsonl")

    # construct a cache from a jsonl file and save to sqlite
    cache = Cache.example()
    cache.write_jsonl("example.jsonl")
    cache_new = Cache.from_jsonl("example.jsonl", db_path="sqlite:///example.db")
    assert cache == cache_new
    os.remove("example.jsonl")
    os.remove("example.db")

    # wrte to a SQLite db and read from it
    c = Cache.example()
    c.write_sqlite_db("sqlite:///example.db")
    cnew = Cache.from_sqlite_db("sqlite:///example.db")
    assert c == cnew

    # a non-valid Cache
    # Cache(data={"poo": "not a CacheEntry"})
    # an empty valid Cache
    cache_empty = Cache()
    # a valid Cache with one entry
    cache = Cache(data={"poo": CacheEntry.example()})
    # __len__
    assert len(cache_empty) == 0
    assert len(cache) == 1
    # __eq__
    assert cache_empty == cache_empty
    assert cache == cache
    assert cache_empty != cache
    # __add__
    assert len(cache_empty + cache) == 1
    assert len(cache_empty + cache_empty) == 1
    assert cache + cache_empty == cache
    assert cache + cache == cache


if __name__ == "__main__":
    import doctest

    doctest.testmod()

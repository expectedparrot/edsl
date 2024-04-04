"""The Cache class is used to store responses from a language model

Why caching?
^^^^^^^^^^^^
Langauge model outputs are expensive to create, both in time and money. 
As such, it is useful to store the outputs of a language model in a cache so that they can be re-used later.

Use cases:
* You can avoid re-running the same queries if a job partial fails, only sending the new queries to the language model
* You can share your cache with others so they can re-run your queries but at no cost
* You can use a common remote cache to avoid re-running queries that others have already run
* Building up training data to train or fine-tune a smaller model
* Build up a public repository of queries and responses so others can learn from them

How it works
^^^^^^^^^^^^
The cache is a dictionary-like object that stores the inputs and outputs of a language model.
Specifically, the cache has an attribute, `data` that is dictionary-like. 

The keys of the cache as hashes of the unique inputs to the language model.
The values are CacheEntry objects, which store the inputs and outputs of the language model.

It can either be a Python in-memory dictionary or dictionary tied to an SQLite3 database.
The default constructor is an in-memory dictionary.
If an SQLite3 database is used, the cache will persist automatically between sessions.

After a session, the cache will have new entries. 
These can be written to a local SQLite3 database, a JSONL file, or a remote server.


Instantiating a new cache
^^^^^^^^^^^^^^^^^^^^^^^^^

This code will instantiate a new cache object but using a dictionary as the data attribute:

In-memory usage
^^^^^^^^^^^^^^^

.. code-block:: python

    from edsl.data.Cache import Cache
    my_in_memory_cache = Cache()

It can then be passed as an object to a `run` method. 

.. code-block:: python

    from edsl import QuestionFreeText
    q = QuestionFreeText.example()
    results = q.run(cache = my_in_memory_cache)

If an in-memory cache is not stored explicitly, the data will be lost when the session is over _unles_ it is written to a file OR
remote caching in instantiated.
More on this later. 

Local persistence for an in-memory cache
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    c = Cache()
    # a bunch of operations
    c.write_sqlite_db("example.db")
    # or 
    c.write_jsonl("example.jsonl")

You can then load the cache from the SQLite3 database or JSONL file using Cache methods.

.. code-block:: python

    c = Cache.from_sqlite_db("example.db")
    # or
    c = Cache.from_jsonl("example.jsonl")

SQLite3Dict for transactions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Instead of using a dictionary as the data attribute, you can use a special dictionary-like object based on 
SQLite3. This will persist the cache between sessions.
This is the "normal" way that a cache is used for runs where no specic cache is passed. 

.. code-block:: python
    from edsl.data.Cache import Cache
    from edsl.data.SQLiteDict import SQLiteDict
    my_sqlite_cache = Cache(data = SQLiteDict("example.db"))

This will leave a SQLite3 database on the user's machine at the file, in this case `example.db` in the current directory.
It will persist between sessions and can be loaded using the `from_sqlite_db` method shown above.

The default SQLite Cache: .edsl_cache/data.db
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default, the cache will be stored in a SQLite3 database at the path `.edsl_cache/data.db`.
You can interact with this cache directly, e.g., 

.. code-block:: bash 

    sqlite3 .edsl_cache/data.db

Remote Cache on Expected Parrot
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
In addition to local caching, the cache can be stored on a remote server---namely the Expected Parrot server.
This is done if the `remote` parameter is set to True AND a valid URL is set in the `EXPECTED_PARROT_CACHE_URL` environment variable.
This is a `.env` file in the root directory of the project.

When remote caching is enabled, the cache will be synced with the remote server at the start end of each `session.`
These sessions are defined by the `__enter__` and `__exit__` methods of the cache object.
When the `__enter__` method is called, the cache will be synced with the remote server by downloading what is missing. 
When the `__exit__` method is called, the new entries will be sent to the remote server, as well as any entries that local 
cache had that were not in the remote cache.

Delayed cache-writing: Useful for remote caching
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Separate from this remote cache syncing, delays can be made in writing to the cache itself. 
By default, the cache will write to the cache immediately after storing a new entry.
However, this can be changed by setting the `immediate_write` parameter to False.

.. code-block:: python

    c = Cache(immediate_write = False)

This is useful when you want to store entries to the cache only after a block of code has been executed.
This is also controlled by using the cache object as a context. 

.. code-block:: python

    with c as cache:
        # readings / writing 
        ...

    # The cache will be written to the cache persistence layer after the block of code has been executed
    

Why this? Well, in some future version, it might be possible to totally eschew the local cache and use a remote cache only.
Remote reads might be very fast, but writes might be slow, so this would be a way to optimize the cache for that use case.        


Idea: 
- We leave an SQLite3 database on user's machine
- When we start a session, we check if there are any updates to the cache on remote server
- If there are, we download them and update the cache

Desired features:
- Hard to corrupt (e.g., if the program crashes)
- Good transactional support
- Can easily combine two caches together w/o duplicating entries
- Can easily fetch another cache collection and add to own
- Can easily use a remote cache w/o changing edsl code 
- Easy to migrate 
- Can deal easily with cache getting too large 
- "Coopable" - could share a smaller cache with another user

- Good defaults
- Can export part of cache that was used for a particular run

Export methods: 
- JSONL
- SQLite3
- JSON

Remote persistence options:
- Database on Expected Parrot 

"""

from __future__ import annotations
import hashlib
import json
import os
import requests
import warnings
from typing import Optional, Union
from edsl.config import CONFIG
from edsl.data.CacheEntry import CacheEntry
from edsl.data.SQLiteDict import SQLiteDict
from edsl.data.RemoteDict import handle_request_exceptions


EDSL_DATABASE_PATH = CONFIG.get("EDSL_DATABASE_PATH")
EXPECTED_PARROT_CACHE_URL = os.getenv("EXPECTED_PARROT_CACHE_URL")

# TODO: What do we want to do if & when there is a mismatch
#       -- if two keys are the same but the values are different?
# TODO: In the read methods, if the file already exists, make sure it is valid.

# TODO: I'd say implement coop as follows:
# - There is a function that instantiates the Coop client (or checks if it is already instantiated) and saves it to a class attribute.
# - The Coop client methods are used in the Cache methods that need it
# - Offload as much of the general errors, such as "this key is not valid" etc to be handled at the level of the Coop client, handle here what is specific to the Cache


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
    ) -> None:
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

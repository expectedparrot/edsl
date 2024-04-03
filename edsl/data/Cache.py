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
This is done if the `remote_backups` parameter is set to True AND a valid URL is set in the `EXPECTED_PARROT_CACHE_URL` environment variable.
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

# TODO: I'd say implement coop as follows:
# - There is a function that instantiates the Coop client (or checks if it is already instantiated) and saves it to a class attribute.
# - The Coop client methods are used in the Cache methods that need it
# - Offload as much of the general errors, such as "this key is not valid" etc to be handled at the level of the Coop client, handle here what is specific to the Cache

from __future__ import annotations
import datetime
import functools
import hashlib
import json
import os
import requests
import tempfile
import warnings
from typing import Optional, Union
from edsl.config import CONFIG
from edsl.data.CacheEntry import CacheEntry
from edsl.data.SQLiteDict import SQLiteDict
from edsl.exceptions import LanguageModelResponseNotJSONError


EDSL_DATABASE_PATH = CONFIG.get("EDSL_DATABASE_PATH")
EXPECTED_PARROT_CACHE_URL = os.getenv("EXPECTED_PARROT_CACHE_URL")


def handle_request_exceptions(reraise=False):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except requests.exceptions.ConnectionError as e:
                print(f"Could not connect to remote server: {e}")
            except requests.exceptions.Timeout as e:
                print(f"Request timed out: {e}")
            except requests.exceptions.HTTPError as e:
                print(f"HTTP error occurred: {e}")
            except requests.exceptions.RequestException as e:
                print(f"An error occurred during the request: {e}")
            except ValueError as e:
                print(f"Invalid data format: {e}")

            if reraise:
                raise

        return wrapper

    return decorator


class Cache:
    """
    A class to represent a cache of responses from a language model.
    """

    data = {}

    def __init__(
        self,
        *,
        data: Optional[Union[SQLiteDict, dict]] = None,
        remote_backups: bool = False,
        immediate_write: bool = True,
        method=None,
    ):
        """
        Instantiates a new Cache.

        :param data: The data to initialize the cache with.
        :param immediate_write: Whether to write to the cache immediately after storing a new entry.
        :param method: (Deprecated and will be removed in the future) The method of storage to use for the cache. Will be removed in future versions.
        """
        self.data = data or {}
        self.remote_backups = remote_backups
        self.immediate_write = immediate_write

        # `new_entries` are created during a __enter__ block
        # `new_entries_to_write_later` stores entries that will be written to the Cache later
        self.new_entries = {}
        self.new_entries_to_write_later = {}

        # sanity checks and warnings
        if self.remote_backups and not EXPECTED_PARROT_CACHE_URL:
            raise ValueError("EXPECTED_PARROT_CACHE_URL is not set")
        if method is not None:
            warnings.warn("Argument `method` is deprecated", DeprecationWarning)
        if any(not isinstance(value, CacheEntry) for value in self.data.values()):
            raise Exception("Not all values are CacheEntry instances")

    def fetch(
        self,
        *,
        model,
        parameters,
        system_prompt,
        user_prompt,
        iteration,
    ) -> Union[None, CacheEntry]:
        """Fetches the response from the cache.

        If there is a cache hit, return the output field from the entity. Otherwise, return None.

        :param model: The model used to generate the response.
        :param parameters: The parameters used to generate the response.
        :param system_prompt: The system prompt used to generate the response.
        :param user_prompt: The user prompt used to generate the response.
        :param iteration: The iteration of the response.


        >>> c = Cache()
        >>> c.fetch(model="gpt-3.5-turbo", parameters="{'temperature': 0.5}", system_prompt="The quick brown fox jumps over the lazy dog.", user_prompt="What does the fox say?", iteration=1)

        >>> c = Cache.example()
        >>> input = c.fetch_input_example()
        >>> c.fetch(**input)
        "The fox says 'hello'"
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
        """Adds an entity to the cache.

        :param model: The model used to generate the response.
        :param parameters: The parameters used to generate the response.
        :param system_prompt: The system prompt used to generate the response.
        :param user_prompt: The user prompt used to generate the response.
        :param response: The response generated by the model.
        :param iteration: The iteration of the response.

        >>> c = Cache()
        >>> input = CacheEntry.store_input_example()
        >>> c.store(**input)
        >>> list(c.data.keys())
        ['55ce2e13d38aa7fb6ec848053285edb4']

        Illustrating the use of delayed write:

        >>> c = Cache(immediate_write = False)
        >>> input = CacheEntry.store_input_example()
        >>> c.store(**input)
        >>> list(c.data.keys())
        []

        Use of context manager to write delayed entries

        >>> delay_cache = Cache(immediate_write = False)
        >>> c = delay_cache.__enter__()
        >>> input = CacheEntry.store_input_example()
        >>> c.store(**input)
        >>> list(c.data.keys()) == []
        True
        >>> delay_cache.__exit__(None, None, None)
        >>> list(delay_cache.data.keys())
        ['55ce2e13d38aa7fb6ec848053285edb4']
        """
        try:
            output = json.dumps(response)
        except json.JSONDecodeError:
            raise LanguageModelResponseNotJSONError

        timestamp = int(datetime.datetime.now(datetime.timezone.utc).timestamp())

        entry = CacheEntry(
            model=model,
            parameters=parameters,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            output=output,
            iteration=iteration,
            timestamp=timestamp,
        )

        key = entry.key
        self.new_entries[key] = entry  # added here no matter what
        if self.immediate_write:
            self.data[key] = entry
        else:
            self.new_entries_to_write_later[key] = entry

    def add_multiple_entries(self, new_data: dict, write_now: bool = True) -> None:
        """
        Add multiple entries to the cache.

        :param new_data: A dictionary of new key-value pairs to add.
        :param write_now: Indicates that the new entries should be added to the cache immediately.

        Example of immediate writing:

        >>> c = Cache()
        >>> data = {'poo': CacheEntry.example(), 'bandits': CacheEntry.example()}
        >>> c.add_multiple_entries(new_data = data)
        >>> c.data['poo'] == CacheEntry.example()
        True

        Example of delayed writing:

        >>> c = Cache()
        >>> data = {'poo': CacheEntry.example(), 'bandits': CacheEntry.example()}
        >>> c.add_multiple_entries(new_data = data, write_now = False)
        >>> c.data
        {}
        >>> c.__exit__(None, None, None)
        >>> c.data['poo'] == CacheEntry.example()
        True
        """
        for key, value in new_data.items():
            if key in self.data:
                if value != self.data[key]:
                    raise Exception("Mismatch in values")
            if not isinstance(value, CacheEntry):
                raise Exception("Wrong type")

        # TODO: What do we want to do if & when there is a mismatch?
        self.new_entries.update(new_data)
        if write_now:
            self.data.update(new_data)
        else:
            self.new_entries_to_write_later.update(new_data)

    def add_from_jsonl(self, filename: str, write_now: bool = True) -> None:
        """Add entries from a JSONL file to the cache.

        :param filename: File to read from.
        :param write_now: Whether to write to cache immediately.

        >>> c = Cache(data = CacheEntry.example_dict())
        >>> c.write_jsonl("example.jsonl")
        >>> cnew = Cache()
        >>> cnew.add_from_jsonl(filename = 'example.jsonl')
        >>> c == cnew
        True
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
        self.add_multiple_entries(new_data=new_data, write_now=write_now)

    def add_from_sqlite(self, db_path: str, write_now: bool = True):
        """Add entries from an SQLite database to the cache.

        :param db_path: Path to the SQLite database.
        :param write_bool: Whether to write immediately.
        """
        # TODO: If the file already exists, make sure it is valid.
        db = SQLiteDict(db_path)
        new_data = {}
        for key, value in db.items():
            new_data[key] = CacheEntry(**value)
        self.add_multiple_entries(new_data=new_data, write_now=write_now)

    @classmethod
    def from_sqlite_db(cls, db_path: str) -> Cache:
        """Return a Cache object from an SQLite database.

        :param db_path: The path to the SQLite database.

        >>> c = Cache.example()
        >>> c.data['poo'] = CacheEntry.example()
        >>> c.write_sqlite_db("example.db")
        >>> cnew = Cache.from_sqlite_db("example.db")
        >>> c == cnew
        True
        """
        return cls(data=SQLiteDict(db_path))

    @classmethod
    def from_jsonl(cls, jsonlfile: str, db_path: str = None) -> "Cache":
        """Return a Cache object from a JSONL file.

        :param jsonlfile: The path to the JSONL file.
        :param db_path: The path to the SQLite database. If None, the cache will be stored in memory, as a dictionary.

        >>> c = Cache.example()
        >>> import tempfile
        >>> with tempfile.NamedTemporaryFile() as f:
        ...     c.write_jsonl(f.name)
        ...     cnew = Cache.from_jsonl(f.name)
        >>> c == cnew
        True
        """
        datastore = {} if db_path is None else SQLiteDict(db_path)
        cache = Cache(data=datastore)
        cache.add_from_jsonl(jsonlfile)
        return cache

    @classmethod
    def from_url(cls, db_path=None) -> "Cache":
        """Return a Cache object from the remote cache."""

        @handle_request_exceptions(reraise=True)
        def coop_fetch_full_remote_cache() -> dict:
            """Fetches the full remote cache."""
            response = requests.get(f"{EXPECTED_PARROT_CACHE_URL}/items/all")
            response.raise_for_status()
            return response.json()

        data = coop_fetch_full_remote_cache()
        db_path = db_path or EDSL_DATABASE_PATH
        db = SQLiteDict(db_path)
        for key, value in data.items():
            db[key] = CacheEntry(**value)
        return Cache(data=db)

    def write_sqlite_db(self, db_path: str) -> None:
        """
        Write the cache to an SQLite database.

        :param db_path: The path to the SQLite database.

        >>> os.remove("example.db")
        >>> c = Cache.example()
        >>> c.write_sqlite_db("example.db")
        >>> cnew = Cache.from_sqlite_db("example.db")
        >>> c == cnew
        True
        """
        ## TODO: Check to make sure not over-writing.
        ## Should be added to SQLiteDict constructor
        new_data = SQLiteDict(db_path)
        for key, value in self.data.items():
            new_data[key] = value

    def write_jsonl(self, filename: str) -> None:
        """Write the cache to a JSONL file.

        :param filename: Filename to write the JSONL to.
        """
        dir_name = os.path.dirname(filename)
        # TODO: Clean up tempfile.
        with tempfile.NamedTemporaryFile(
            mode="w", dir=dir_name, delete=False
        ) as tmp_file:
            for key, raw_value in self.data.items():
                value = (
                    raw_value
                    if not hasattr(raw_value, "to_dict")
                    else raw_value.to_dict()
                )
                tmp_file.write(json.dumps({key: value}) + "\n")
            temp_name = tmp_file.name
        try:
            os.replace(temp_name, filename)
        finally:
            if os.path.exists(temp_name):
                os.remove(temp_name)
                os.replace(temp_name, filename)

    @classmethod
    def example(cls) -> "Cache":
        """Return an example Cache."""
        return cls(data={CacheEntry.example().key: CacheEntry.example()})

    @staticmethod
    def all_key_hash(key_list) -> str:
        """Return a hash of all the keys in the cache."""
        # TODO: Check to make sure keys are unique.
        all_keys_string = "".join(sorted(key_list))
        return hashlib.md5(all_keys_string.encode()).hexdigest()

    def remote_cache_matches(self) -> bool:
        """Check the remote cache for any updates."""

        @handle_request_exceptions()
        def coop_remote_cache_matches(data) -> bool:
            current_all_key_hash = Cache.all_key_hash(data.keys())
            response = requests.get(
                f"{EXPECTED_PARROT_CACHE_URL}/compare_hash/{current_all_key_hash}"
            )
            response.raise_for_status()
            return response.json()["match"]

        return coop_remote_cache_matches(self.data)

    def send_missing_entries_to_remote(self):
        """Send missing entries to the remote server."""

        # TODO: We want a function that computes missing entries and then only sends those; this
        # just sends everything.

        @handle_request_exceptions
        def coop_send_missing_entries_to_remote_cache(data: dict) -> None:
            items = [
                {"key": key, "item": value.to_dict()} for key, value in data.items()
            ]
            response = requests.post(
                f"{EXPECTED_PARROT_CACHE_URL}/items/batch", json=items
            )
            response.raise_for_status()

        coop_send_missing_entries_to_remote_cache(self.data)

    def get_missing_entries_from_remote(self):
        """Get missing entries from the remote server."""

        def coop_get_missing_entries_from_remote(data: dict) -> dict:
            """This function should take the current cache as input and then figure out, with the
            remote server, what entities it needs to get synced up.

            TODO:
            This could mean just sending the 'top hash' of a Merkle tree or the list of key values.

            Right now, it's just retruning everything.
            """
            response = requests.get(f"{EXPECTED_PARROT_CACHE_URL}/items/all")
            if response.status_code == 404:
                raise KeyError(f"Key '{key}' not found.")
            response.raise_for_status()
            data = response.json()
            return data

        locally_missing = coop_get_missing_entries_from_remote(self.data)
        for key, value in locally_missing.items():
            if key not in self.data:
                self.data[key] = CacheEntry(**value)

    def sync_local_and_remote(self, verbose: bool = False):
        """Sync the local and remote caches."""
        if self.remote_cache_matches():
            if verbose:
                print("Remote and local caches are the same")
        else:
            if verbose:
                print("Caches are different; getting missing entries from remote")
            self.get_missing_entries_from_remote()
            if verbose:
                print("Sending missing entries to remote")

            # TODO: This should actually happen *after* on exit
            self.send_missing_entries_to_remote()

    def __enter__(self):
        """This is run when a context is entered.

        >>> new_cache = Cache()
        >>> with new_cache as cache:
        ...    cache.data['a'] = Cache.example()
        >>> new_cache.data['a'] == Cache.example()
        True
        """

        def coop_backup_enabled(value) -> bool:
            # TODO: Presumably we would have some some way to indicate that
            # the user wants remote backups to happen.
            return value

        # Do something smarter here
        if coop_backup_enabled(self.remote_backups):
            self.sync_local_and_remote()

        return self

    def send_new_entries_to_remote(self):
        # TODO: So here it would be something like
        # self.coop.send_to_remote(self.new_entries)

        def coop_send_to_remote(new_entries: dict) -> None:
            """Send new entries to the remote cache."""
            items = [
                {"key": key, "item": value.to_dict()}
                for key, value in new_entries.items()
            ]
            response = requests.post(
                f"{EXPECTED_PARROT_CACHE_URL}/items/batch", json=items
            )
            response.raise_for_status()

        coop_send_to_remote(self.new_entries)

    def __exit__(self, exc_type, exc_value, traceback):
        for key, entry in self.new_entries_to_write_later.items():
            self.data[key] = entry

        # TODO: Use a coop function to check if remote backup enabled.
        if self.remote_backups:
            self.send_new_entries_to_remote()
            # import requests
            # items = [{"key": key, "item": value.to_dict()} for key, value in self.new_entries.items()]
            # try:
            #     response = requests.post(f"{EXPECTED_PARROT_CACHE_URL}/items/batch", json=items)
            #     response.raise_for_status()
            # except requests.exceptions.ConnectionError as e:
            #     print(f"Could not connect to remote server: {e}")

    def to_dict(self):
        return {k: v.to_dict() for k, v in self.data.items()}

    @classmethod
    def from_dict(cls, data, method="memory"):
        data = {k: CacheEntry.from_dict(v) for k, v in data}
        return cls(data=data)

    ####################
    # DUNDER
    ####################
    def __len__(self):
        """Returns the number of CacheEntry objects in the Cache."""
        return len(self.data)

    def __eq__(self, other_cache: "Cache") -> bool:
        """
        Checks if two Cache objects are equal.
        - Doesn't verify their values are equal, just that they have the same keys.
        """
        if not isinstance(other_cache, Cache):
            return False
        return self.data.keys() == other_cache.data.keys()

    def __add__(self, other: "Cache"):
        """Combines two caches."""
        if not isinstance(other, Cache):
            raise ValueError("Can only add two caches together")
        self.data.update(other.data)
        return self

    def __repr__(self):
        """Returns a string representation of the Cache object."""
        return (
            f"Cache(data = {repr(self.data)}, immediate_write={self.immediate_write})"
        )

    ####################
    # EXAMPLES
    ####################
    def fetch_input_example(self) -> dict:
        """Create an example input for a 'fetch' operation."""
        return CacheEntry.fetch_input_example()

    ####################
    # TODO: REMOVE?
    ####################

    # TODO: Doesn't seem to be used anywhere
    # @property
    # def last_insertion(self) -> int:
    #     """
    #     Get the timestamp of the last insertion into the cache.

    #     >>> c = Cache()
    #     >>> input = CacheEntry.store_input_example()
    #     >>> c.store(**input)
    #     >>> insert_time = list(c.data.values())[0].timestamp
    #     >>> c.last_insertion - insert_time
    #     0
    #     """
    #     keys = list(self.data.keys())
    #     if len(keys) > 0:
    #         last_key = keys[-1]
    #         entry = self.data[last_key]
    #         return getattr(entry, "timestamp")
    #     else:
    #         raise Exception("Cache is empty!")


def main():
    from edsl.data.Cache import Cache
    from edsl.data.CacheEntry import CacheEntry

    # a non-valid Cache
    Cache(data={"poo": "not a CacheEntry"})
    # an empty valid Cache
    cache_empty = Cache()
    # a valid Cache with one entry
    cache = Cache(data={"poo": CacheEntry.example()})

    # __len__
    len(cache_empty) == 0
    len(cache) == 1
    # __eq__
    cache_empty == cache_empty
    cache == cache
    cache_empty != cache
    # __add__
    len(cache_empty + cache) == 1
    len(cache_empty + cache_empty) == 0
    cache + cache_empty == cache
    cache + cache == cache


if __name__ == "__main__":
    import doctest

    doctest.testmod()

    if False:
        # base_url = "https://f61709b5-4cdf-487d-a30c-a803ab910ca1-00-27digq3c8e2zg.worf.replit.dev"
        # cache = Cache(data = RemoteDict(base_url = base_url))
        # cache = Cache.from_url(base_url = base_url)

        cache = Cache()

        from edsl import QuestionFreeText, QuestionMultipleChoice

        # q = QuestionFreeText.example()
        # results = q.run(cache = cache)

        # q2 = QuestionMultipleChoice.example()
        # results = q2.run(cache = cache, progress_bar = True)

        #    with cache as c:
        from edsl import Model, Scenario

        m = Model(Model.available()[0])
        numbers = range(150, 250)
        scenarios = [Scenario({"number": number}) for number in numbers]
        q = QuestionFreeText(
            question_text="Is {{number}} prime?", question_name="prime"
        )
        results = q.by(m).by(scenarios).run(cache=cache, progress_bar=True)

        # data = {'poo': CacheEntry.example()}

        # c = Cache(data = data)
        # c.data

        # print("Printing weird example")
        # c.write_sqlite_db("weird_example.db")

        # print(c.last_insertion)

        # delay_cache = Cache(immediate_write = False)
        # with delay_cache as c:
        #     input = CacheEntry.store_input_example()
        #     c.store(**input)
        #     print("Keys are currently:", list(c.data.keys()))

        # print("Keys are now:", delay_cache.data.keys())

        ##c.fetch(**CacheEntry.fetch_input_example())

        # cache = Cache.from_jsonl('cache.jsonl')
        # from edsl import QuestionFreeText
        # results = QuestionFreeText.example().run(cache = cache)

        # start = time.monotonic()
        # for i in range(1_000_000):
        #     c = CacheEntry.example()
        #     c.iteration += i
        #     cache.add_to_jsonl(c)
        # end = time.monotonic()
        # print(f"Time: {end - start} for 1_000_000 entries")
        # # c.save('cache.json')

        # cache.to_jsonl(filename = 'test_cache.jsonl')

        # new_cache = Cache.load('cache.json')

        # ce = CacheEntry("gpt-3.5-turbo", "{'temperature': 0.5}", "The quick brown fox jumps over the lazy dog.", "What does the fox say?", "The fox says 'hello'", 1)
        # ce.gen_key()

        # c = Cache()
        # c._store_memory("gpt-3.5-turbo", "{'temperature': 0.5}", "The quick brown fox jumps over the lazy dog.", "What does the fox say?", "The fox says 'hello'", 1)

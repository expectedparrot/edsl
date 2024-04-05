Data
====
The `Cache` class is used to store responses from a language model.

Why caching?
^^^^^^^^^^^^
Language model outputs are expensive to create, both in terms of time and money. 
As such, it is useful to store the outputs of a language model in a cache so that they can be re-used later.

Use cases:

* Avoid re-running the same queries if a job fails only partially, only sending the new queries to the language model.
* Share your cache with others so they can re-run your queries at no cost.
* Use a common remote cache to avoid re-running queries that others have already run.
* Build up training data to train or fine-tune a smaller model.
* Build up a public repository of queries and responses so others can learn from them.

How it works
^^^^^^^^^^^^
The `Cache` is a dictionary-like object that stores the inputs and outputs of a language model.
Specifically, the cache has an attribute, `data`, that is dictionary-like. 

The keys of the cache are hashes of the unique inputs to the language model.
The values are `CacheEntry` objects, which store the inputs and outputs of the language model.

It can either be a Python in-memory dictionary or dictionary tied to a SQLite3 database.
The default constructor is an in-memory dictionary.
If an SQLite3 database is used, the cache will persist automatically between sessions.

After a session, the cache will have new entries. 
These can be written to a local SQLite3 database, a JSONL file, or a remote server.

Instantiating a new cache
^^^^^^^^^^^^^^^^^^^^^^^^^
This code will instantiate a new cache object but using a dictionary as the data attribute.

In-memory usage
^^^^^^^^^^^^^^^

.. code-block:: python

    from edsl.data.Cache import Cache
    my_in_memory_cache = Cache()

It can then be passed as an object to a `run` method:

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


Remote cache on Expected Parrot
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
In addition to local caching, the cache can be stored on a remote server---namely, the Expected Parrot server.
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
    

Why this? In a future version, it may be possible to totally eschew the local cache and use a remote cache only.
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

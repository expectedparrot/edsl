.. _caching:

Caching LLM Calls
=================
The `Cache` class is used to store responses from a language model so that they can easily be retrieved, reused and shared.

.. raw:: html

   <i>What is a cache?</i> (<a href="https://en.wikipedia.org/wiki/Cache_(computing)" target="_blank">Wikipedia</a>)

   <br><br>


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
A `Cache` is a dictionary-like object that stores the inputs and outputs of a language model.
Specifically, a cache has an attribute, `data`, that is dictionary-like. 

The keys of a cache are hashes of the unique inputs to a language model.
The values are `CacheEntry` objects, which store the inputs and outputs of a language model.

A cache can be stored as either a Python in-memory dictionary or a dictionary connected to a SQLite3 database.
The default constructor is an in-memory dictionary.
If a SQLite3 database is used, a cache will persist automatically between sessions.
You can also specify that a cache be used for a specific session, in which case it will not persist between sessions.

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


If an in-memory cache is not stored explicitly, the data will be lost when the session is over--unless it is written to a file or remote caching is instantiated.
More on this below. 


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



Setting a session cache 
^^^^^^^^^^^^^^^^^^^^^^^
The `set_session_cache` function is used to set the cache for a session:

.. code-block:: python

   from edsl import set_session_cache
   from edsl.data import Cache
   set_session_cache(Cache())


The cache can be set to a specific cache object, or it can be set to a dictionary or SQLite3Dict object.

.. code-block:: python

   from edsl import set_session_cache
   from edsl.data import Cache, SQLiteDict
   set_session_cache(Cache(data = SQLiteDict("example.db")))
   # or
   set_session_cache(Cache(data = {}))


This will set the cache for the current session, and you do not need to pass the cache object to the `run` method during the session.

The `unset_session_cache` function is used to unset the cache for a session:

.. code-block:: python

   from edsl import unset_session_cache
   unset_session_cache()


This will unset the cache for the current session, and you will need to pass the cache object to the `run` method during the session.


For developers
^^^^^^^^^^^^^^

Delayed cache-writing: Useful for remote caching
------------------------------------------------
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
   



Cache class 
-----------

.. automodule:: edsl.data.Cache
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: codebook, data, main

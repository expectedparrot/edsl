.. _caching:

Caching LLM Calls
=================
The `Cache` class is used to store responses from a language model so that they can easily be retrieved, reused and shared.

.. raw:: html

   <i>What is a cache?</i> (<a href="https://en.wikipedia.org/wiki/Cache_(computing)" target="_blank">Wikipedia</a>)

   <br><br>


Why caching?
------------

Language model outputs are expensive to create, both in terms of time and money. 
As such, it is useful to store them in a cache so that they can be shared or reused later.

Use cases:

* Avoid rerunning questions when a job fails only partially, by only resending unanswered questions to a language model.
* Share your cache with others so they can rerun your questions at no cost.
* Use a common remote cache to avoid rerunning questions that others have already run.
* Build up training data to train or fine-tune a smaller model.
* Build up a public repository of questions and responses so others can learn from them.


How it works
------------

A `Cache` is a dictionary-like object that stores the inputs and outputs of a language model.
Specifically, a cache has an attribute, `data`, that is dictionary-like. 

The keys of a cache are hashes of the unique inputs to a language model.
The values are `CacheEntry` objects, which contains the inputs and outputs.

A cache can be stored as either a Python in-memory dictionary or a dictionary connected to a SQLite3 database.
The default constructor is an in-memory dictionary.
If a SQLite3 database is used, a cache will persist automatically between sessions.
You can also specify that a cache be used for a specific session, in which case it will not persist between sessions.

After a session, the cache will have new entries from any new jobs that have been run during the session. 
These can be written to a local SQLite3 database, a JSONL file, or a remote server.


Generating a cache
------------------

A cache is automatically created whenever results are generated for a question or survey.
This cache is specific to the results and is attached to the results object.
It can be accessed using the `cache` attribute of the results object.

For example:

.. code-block:: python

   from edsl import QuestionNumerical, Model

   m = Model("gemini-1.5-flash")

   q = QuestionNumerical(
      question_name = "random",
      question_text = "Please give me a random number between 1 and 100."
   )

   results = q.by(m).run()

   results.cache


Example output:

.. list-table::
   :header-rows: 1

   * - model 
     - parameters
     - system_prompt
     - user_prompt
     - output
     - iteration
     - timestamp
     - cache_key
   * - gemini-1.5-flash
     - {'temperature': 0.5, 'topP': 1, 'topK': 1, 'maxOutputTokens': 2048, 'stopSequences': []}
     - nan
     - Please give me a random number between 1 and 100. This question requires a numerical response in the form of an integer or decimal (e.g., -12, 0, 1, 2, 3.45, ...). Respond with just your number on a single line. If your response is equivalent to zero, report '0' After the answer, put a comment explaining your choice on the next line.
     - {"candidates": [{"content": {"parts": [{"text": "87\n# This is a randomly generated number between 1 and 100.\n"}], "role": "model"}, "finish_reason": 1, "safety_ratings": [{"category": 8, "probability": 1, "blocked": false}, {"category": 10, "probability": 1, "blocked": false}, {"category": 7, "probability": 1, "blocked": false}, {"category": 9, "probability": 1, "blocked": false}], "avg_logprobs": -0.03539780080318451, "token_count": 0, "grounding_attributions": []}], "usage_metadata": {"prompt_token_count": 97, "candidates_token_count": 20, "total_token_count": 117, "cached_content_token_count": 0}}
     - 0
     - 1737491116
     - 7f057154c60a1b9ae343b0634fe7a370


We can also see that the results object include columns of information about the cache:

.. code-block:: python

   results.columns 

Output:

.. code-block:: python

.. list-table::
   :header-rows: 1

   * - 0 
     - agent.agent_index
   * - 1 
     - agent.agent_instruction
   * - 2 
     - agent.agent_name
   * - 3 
     - answer.random
   * - 4 
     - cache_keys.random_cache_key
   * - 5 
     - cache_used.random_cache_used
   * - 6 
     - comment.random_comment
   * - 7 
     - generated_tokens.random_generated_tokens
   * - 8 
     - iteration.iteration
   * - 9 
     - model.maxOutputTokens
   * - 10
     - model.model
   * - 11
     - model.model_index
   * - 12
     - model.stopSequences
   * - 13
     - model.temperature
   * - 14
     - model.topK
   * - 15
     - model.topP
   * - 16
     - prompt.random_system_prompt
   * - 17
     - prompt.random_user_prompt
   * - 18
     - question_options.random_question_options
   * - 19
     - question_text.random_question_text
   * - 20
     - question_type.random_question_type
   * - 21
     - raw_model_response.random_cost
   * - 22
     - raw_model_response.random_one_usd_buys
   * - 23
     - raw_model_response.random_raw_model_response
   * - 24
     - scenario.scenario_index


The `cache_keys` column contains the cache key for each question.
It is a unique identifier for the cache entry, and can be used to retrieve the cache entry later.

For example, here we retrieve the cache key and use it when running a survey that includes the relevant question:

.. code-block:: python

   my_cache_key = results.select("cache_keys.random_cache_key").first()
   
   from edsl import QuestionFreeText, QuestionNumerical, Survey, Model

   m = Model("gemini-1.5-flash")

   q1 = QuestionNumerical(
      question_name = "random",
      question_text = "Please give me a random number between 1 and 100."
   )

   q2 = QuestionFreeText(
      question_name = "explain",
      question_text = "How does an AI choose a random number?"
   )

   survey = Survey(questions = [q1,q2])

   new_results = survey.by(m).run(cache_key = my_cache_key)


We could also pass the cache itself:

.. code-block:: python 

   my_cache = results.cache 

   new_results = survey.by(m).run(cache = my_cache)


Instantiating a new cache
-------------------------

This code will instantiate a new cache object but using a dictionary as the data attribute.

In-memory usage
^^^^^^^^^^^^^^^

.. code-block:: python

   from edsl import Cache
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

Instead of using a dictionary as the data attribute, you can use a special dictionary-like object based on SQLite3. 
This will persist the cache between sessions.
This is the "normal" way that a cache is used for runs where no specic cache is passed. 

.. code-block:: python

   from edsl import Cache
   from edsl.data.SQLiteDict import SQLiteDict
   my_sqlite_cache = Cache(data = SQLiteDict("example.db"))



This will leave a SQLite3 database on the user's machine at the file, in this case `example.db` in the current directory.
It will persist between sessions and can be loaded using the `from_sqlite_db` method shown above.


Default SQLite Cache: .edsl_cache/data.db
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

By default, the cache will be stored in a SQLite3 database at the path `.edsl_cache/data.db`.
You can interact with this cache directly, e.g., 

.. code-block:: bash 

   sqlite3 .edsl_cache/data.db


Setting a session cache 
^^^^^^^^^^^^^^^^^^^^^^^

The `set_session_cache` function is used to set the cache for a session:

.. code-block:: python

   from edsl import Cache, set_session_cache
   set_session_cache(Cache())


The cache can be set to a specific cache object, or it can be set to a dictionary or SQLite3Dict object.

.. code-block:: python

   from edsl import Cache, set_session_cache
   from edsl.data import SQLiteDict
   set_session_cache(Cache(data = SQLiteDict("example.db")))
   # or
   set_session_cache(Cache(data = {}))


This will set the cache for the current session, and you do not need to pass the cache object to the `run` method during the session.

The `unset_session_cache` function is used to unset the cache for a session:

.. code-block:: python

   from edsl import unset_session_cache
   unset_session_cache()


This will unset the cache for the current session, and you will need to pass the cache object to the `run` method during the session.


Avoiding cache persistence 
^^^^^^^^^^^^^^^^^^^^^^^^^^

We can avoid cache persistence by passing `cache=False` to the `run` method:

.. code-block:: python

   from edsl import QuestionFreeText

   q = QuestionFreeText.example()

   results = q.run(cache = False)


For developers
--------------

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
   


Cache class 
-----------

.. automodule:: edsl.data.Cache
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: codebook, data, main

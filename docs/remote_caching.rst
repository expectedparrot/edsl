.. _remote_caching:

Remote Caching
===============

Getting started
------------------

Remote caching allows you to store responses from language models on our server.
To get started, you will need to create a Coop account and store your 
Expected Parrot API key in a *.env* file. See  :ref:`coop` for instructions.

When that's done, you can go to the `Coop API <https://www.expectedparrot.com/home/api>`_
page and turn remote caching on:

.. image:: static/coop_toggle_remote_cache.png
  :alt: Remote cache toggle on the Coop web app
  :align: center
  :width: 300px

Now, when you invoke the ``run`` method on EDSL, we will automatically 
cache your language model responses on the server.

Let's try it out. Note that we are using an empty in-memory cache here for 
demonstration purposes, but this code should work with any local cache mentioned
in :ref:`caching`.

.. code-block:: python

  from edsl import Cache
  from edsl.questions import QuestionMultipleChoice, QuestionFreeText

  survey = Survey(questions=[QuestionMultipleChoice.example(), QuestionFreeText.example()])

  result = survey.run(cache=Cache())

We can look at the `Coop remote cache logs <https://www.expectedparrot.com/home/remote-cache>`_
to verify that our results were cached successfully:

.. image:: static/coop_remote_cache_logs_1.png
  :alt: Logs showing 2 remote cache entries on the Coop web app
  :align: center
  :width: 650px

If you see more than 2 uploaded entries, it's likely that your local cache
already contained some entries (see :ref:`syncing` for more details).

Clearing the cache
-------------------

You are currently allowed to store a maximum of 50,000 entries in the remote cache.
Trying to exceed this limit will raise an ``APIRemoteCacheError``.

If you need to clear the remote cache, you can do so with the following command:

.. code-block:: python

  # Remove all entries from the remote cache
  coop.remote_cache_clear()

Output:

.. code-block:: python

  {'status': 'success', 'deleted_entry_count': 2}

You can also clear the logs shown on Coop as follows:

.. code-block:: python

  coop.remote_cache_clear_log()


.. _syncing:

Syncing
------------------

Behind the scenes, remote caching involves the following steps:

  * Find out which local cache entries are missing from the remote cache, and vice versa.
  * Update the local cache with entries from the remote cache.
  * Run the EDSL survey.
  * Update the remote cache with entries from the local cache, along with the new entries from the survey.

Let's look deeper at how syncing works. To start, we'll create a local cache 
with some example entries. We'll also add examples to the remote cache.

.. code-block:: python

  from edsl import CacheEntry, Cache, Coop

  local_entries = [CacheEntry.example(randomize=True) for _ in range(10)]
  remote_entries = [CacheEntry.example(randomize=True) for _ in range(15)]

  # Add entries to local cache
  c = Cache()
  c.add_from_dict({entry.key: entry for entry in local_entries})

  # Add entries to remote cache
  coop = Coop()
  coop.remote_cache_create_many(remote_entries)


We now have 10 entries in the local cache and 15 in the remote cache.
Let's run a survey:

.. code-block:: python

  from edsl import Survey
  from edsl.questions import QuestionCheckBox, QuestionNumerical

  survey = Survey(questions=[QuestionCheckBox.example(), QuestionNumerical.example()])

  result = survey.run(cache=c, verbose=True)


Setting the ``verbose`` flag to True provides us with some helpful output:

.. code-block::

  Updating local cache with 15 new entries from remote...
  Local cache updated!
  Running job...
  Job completed!
  Updating remote cache with 12 new entries...  # 10 from local, 2 from survey
  Remote cache updated!
  There are 27 entries in the local cache.

From this output, we see that the local cache has been synced with the remote cache. 
We should now have 27 entries in both caches.

We can verify that there are 27 entries in the remote cache by viewing the
remote cache logs:

.. image:: static/coop_remote_cache_logs_2.png
  :alt: Logs showing 27 remote cache entries on the Coop web app
  :align: center
  :width: 650px

In addition to the total entries, the logs show us the details of each 
remote cache operation:
 
  * Uploading 15 entries to remote cache  (our initial call to ``remote_cache_create_many``)
  * Downloading 15 entries from remote to local (part of our ``run`` call)
  * Uploading of 12 entries from local to remote (part of our ``run`` call)

Remote cache methods
--------------

Once you've activated remote caching on Coop, we will automatically send your LLM responses
to the server when you run a job.

However, if you need to interact with the remote cache manually, we 
have the following methods.

Coop class
^^^^^^^^^^^^^^

.. autoclass:: edsl.coop.coop.Coop
  :members: remote_cache_create, remote_cache_create_many, remote_cache_get, remote_cache_clear, remote_cache_clear_log
  :undoc-members:
  :show-inheritance:
  :special-members:
  :exclude-members: 

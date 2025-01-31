.. _remote_caching:

Remote Caching
===============

Remote caching allows you to store responses from language models at the Expected Parrot server.

*Note:* You must have a Coop account in order to use remote inference.
By using remote inference you agree to terms of use of service providers, which Expected Parrot may accept on your behalf and enforce in accordance with its own terms of use: https://www.expectedparrot.com/terms.*


Activating remote caching
-------------------------

1. Log into your `Coop account <https://www.expectedparrot.com/login>`_.

2. Navigate to your `Settings <a href="https://www.expectedparrot.com/home/settings>`_ page and toggle on the slider for *Remote caching*.

.. image:: static/settings.png
  :alt: Toggle on remote inference
  :align: center
  :width: 100%
  

.. raw:: html

  <br>


Your Expected Parrot API key is automatically stored at your `Keys <https://www.expectedparrot.com/home/keys>`_ page.
If you are managing your keys in a local `.env` file instead, copy your key to the file.
See instructions on managing keys in the :ref:`api_keys` section.

You can regenerate your key at any time.


Using remote caching
--------------------

When remote caching is on, the results of any question or survey that you run will be stored automatically on the Expected Parrot server.

You can use remote caching by passing a `Cache` object to the `run` method of a survey.


Example 
^^^^^^^

Here we import the `Cache` module in order to pass a `Cache()` object when we call the `run` method on a survey.
Note that we use an empty in-memory cache for demonstration purposes; the code can also be used with an existing local cache. 
See :ref:`caching` for more details on caching results locally.

.. code-block:: python

  from edsl import QuestionMultipleChoice, QuestionFreeText, Survey, Cache

  survey = Survey(questions=[QuestionMultipleChoice.example(), QuestionFreeText.example()])

  result = survey.run(cache=Cache(), remote_cache_description="Example survey #1")


Remote cache logs
-----------------

We can inspect `Coop remote cache logs <https://www.expectedparrot.com/home/remote-cache>`_ to verify that our results were cached successfully.
The logs will show that we have 2 remote cache entries:

.. image:: static/coop_remote_cache_logs_1.png
  :alt: Logs showing 2 remote cache entries on the Coop web app
  :align: center
  :width: 650px

.. raw:: html

  <br>


We can inspect the details of individual entries by clicking on **View entries**.

.. image:: static/coop_remote_cache_entries_1.png
  :alt: Page displaying the code for a remote cache entry on the Coop web app
  :align: center
  :width: 650px

.. raw:: html

  <br>


Bulk remote cache operations
----------------------------

The remote cache logs page allows you to perform bulk operations on your cache entries:

  * **Send to cache:** This creates unlisted cache objects on Coop that will appear at your `Remote Cache <https://www.expectedparrot.com/home/caches/>`_ page. After an object has been created you can change the visibility to public or private.
  * **Delete:** This deletes entries from your remote cache. This operation is currently irreversible, so use it with caution!

When performing a bulk remote cache operation, you can select from one of three targets:

  * **Selected entries:** The entries you've selected via checkbox.
  * **Search results:** The entries that match your search query. Search queries are case insensitive. They match either the raw model output or the cache entry description. 
  * **Remote cache:** All of the entries in your remote cache. 


Clearing the cache programatically
----------------------------------

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



Remote cache methods
--------------------

When remote caching is activated, EDSL will automatically send model responses to the server when you run a job
(i.e., you do not need to execute methods manually).

If you want to interact with the remote cache programatically, you can use the following methods:


Coop class
^^^^^^^^^^

.. autoclass:: edsl.coop.coop.Coop
  :members: remote_cache_create, remote_cache_create_many, remote_cache_get, remote_cache_clear, remote_cache_clear_log
  :undoc-members:
  :show-inheritance:
  :special-members:
  :exclude-members: 

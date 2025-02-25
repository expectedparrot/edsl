.. _remote_caching:

Remote Caching
==============

*The universal remote cache is still in development. 
This page will be updated and users will be notified via email when it is live.
For now, your legacy remote cache is still available. 
Please see below for details on how it works.*

Remote caching allows you to store responses from language models at the Expected Parrot server, and retrieve responses to questions that have already been run.
The logs of your remote surveys and results are also automatically stored at the Expected Parrot server, and can be viewed and managed at the `Cache <https://www.expectedparrot.com/home/remote-cache>`_ page of your account.

If you want to use your local cache or another cache that is not part of the universal remote cache, you must use local inference (run your surveys locally).

*Note: You must have a Coop account in order to use remote inference and caching.
By using remote inference you agree to any terms of use of service providers, which Expected Parrot may accept on your behalf and enforce in accordance with our terms of use.*


How it works 
------------

Activating remote caching
-------------------------

Remote caching is automatically activated when remote inference is activated.
See instructions on activating remote inference at the :ref:`remote_inference` section.

Whenever you run a survey remotely at the Expected Parrot server, your results are also cached at the server.
You can access them at your `Cache <https://www.expectedparrot.com/home/remote-cache>`_ page or from your workspace (see examples of methods below).


Legacy remote cache
-------------------

Your legacy remote cache is a private resource that is available to you at your Coop account.
It contains responses to questions that you have run at the Expected Parrot server and is accessible at the `Cache <https://www.expectedparrot.com/home/remote-cache>`_ page of your account.

By default, when you run a survey at the Expected Parrot server your survey results will draw from your legacy remote cache.
If your survey includes a question that has been run before, the stored response is retrieved from your legacy remote cache and included in your results, at no cost to you.
If a question has not been run before, a new response is generated and included in your results and the legacy remote cache.
If you want to draw fresh responses (i.e., you do not want to draw any responses from your legacy remote cache), you can pass a parameter `fresh=True` to the `run()` method.

*Note: Your legacy remote cache is not available for local inference (surveys run on your own machine). 
When the universal remote cache is live, your legacy remote cache will remain available at your account for 30 days. 
After 30 days your cache entries will be removed and emailed to you. 
If you would like to have your legacy remote cache entries available in the universal remote cache, please contact us for free credits for rerunning your surveys to regenerate the responses and add them to the universal remote cache.*


Universal remote cache 
----------------------

*This feature is in progress. This page will be updated and users will be notified when it is live.*

The universal remote cache is a shared resource that is available to all users.
It contains responses to all questions that have been run at the Expected Parrot server.
By default, when you run a survey at the Expectecd Parrot server your survey results will draw from the universal remote cache.
If your survey includes a question that has been run before, the stored response is retrieved from the universal remote cache and included in your results, at no cost to you.
If a question has not been run before, a new response is generated and included in your results and added to the universal remote cache.


Fresh responses 
^^^^^^^^^^^^^^^

If you want to draw all fresh responses, you can pass a parameter `fresh=True` to the `run()` method. 
Your results object will still have a cache automatically attached to it, and the universal remote cache will still be updated with any new responses that are generated.


Features of the universal remote cache 
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The universal remote cache offers the following features:

* **Free access:** It is free to use and available to all users, regardless of whether you are running surveys remotely with your own keys for language models or an Expected Parrot API key.

* **Free storage & retrieval:** There is no limit on the number of responses that you can add to the universal remote cache or retrieve from it.

* **Automatic updates:** It is automatically updated whenever a survey is run remotely.

* **Multiple responses:** If a fresh response is generated for a question that is different from a response already stored in the universal remote cache, the new response is added with an iteration index.

* **No deletions:** You cannot delete entries from the universal remote cache.

* **No manual additions:** You cannot manually add entries. The only way to add responses to the universal remote cache is by running a survey remotely at the Expected Parrot server.

* **Sharing & reproducibility:** A new cache is automatically attached to each results object, which can be posted and shared with other users at the Coop. 

* **Privacy:** It is not queryable. You must run a survey to retrieve responses from the universal remote cache.

*Note:* The universal remote cache is not available for local inference (surveys run on your own machine).


Using your remote cache
-----------------------

You can view and search all of your remote cache entries and logs at your `Cache <https://www.expectedparrot.com/home/remote-cache>`_ page.
These entries include all of the responses to questions that you have run remotely and generated or retrieved from the universal remote cache, and all the logs of your remote surveys. 

For example, here we run a survey with remote caching activated, and pass a description to readily identify the job at Coop:

.. code-block:: python

  from edsl import Model, QuestionFreeText, Survey

  m = Model("gemini-1.5-flash")

  q = QuestionFreeText(
    question_name = "prime",
    question_text = "Is 2 a prime number?"
  )

  survey = Survey(questions = [q])

  results = survey.by(m).run(
    remote_inference_description = "Example survey", # optional
    remote_inference_visibility = "public" # optional
  )


We can see the job has been added:

.. image:: static/home-remote-cache-logs.png
  :alt: Page displaying a remote cache at the Coop web app
  :align: center
  :width: 100%


.. raw:: html

  <br>


We can view the details of each cache entry:

.. image:: static/home-remote-cache-entry-details.png
  :alt: Page displaying the code for a remote cache entry on the Coop web app
  :align: center
  :width: 100%

.. raw:: html

  <br>



Reproducing results 
^^^^^^^^^^^^^^^^^^^

When you share a results object (e.g., post it publicly at Coop or share it privately with other users) the cache attached to it is automatically shared with it.
This can be useful if you want to share a specific historic cache for a survey or project (e.g., to allow other users to reproduce your results).
You can inspect the cache for a results object by calling the `cache` property on a results object.

For example, here we inspect the cache for the survey that we ran above:

.. code-block:: python

  results.cache 


Output:

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
     - Is 2 a prime number?
     -	{"candidates": [{"content": {"parts": [{"text": "Yes, 2 is a prime number. It's the only even prime number.\n"}], "role": "model"}, "finish_reason": 1, "safety_ratings": [{"category": 8, "probability": 1, "blocked": false}, {"category": 10, "probability": 1, "blocked": false}, {"category": 7, "probability": 1, "blocked": false}, {"category": 9, "probability": 1, "blocked": false}], "avg_logprobs": -0.0006228652317076921, "token_count": 0, "grounding_attributions": []}], "usage_metadata": {"prompt_token_count": 7, "candidates_token_count": 20, "total_token_count": 27, "cached_content_token_count": 0}, "model_version": "gemini-1.5-flash"}	
     - 0	
     - 1738759640	
     - b939c0cf262061c7aedbbbfedc540689


See :ref:`caching` for more details on caching results locally.


Remote cache methods
--------------------

When remote caching is activated, EDSL will automatically send responses to the server when you run a job
(i.e., you do not need to execute methods manually).

If you want to interact with the remote cache programatically, you can use the following methods:


Coop class
^^^^^^^^^^

.. autoclass:: edsl.coop.coop.Coop
  .. :members: remote_cache_create, remote_cache_create_many, remote_cache_get, remote_cache_clear, remote_cache_clear_log
  :undoc-members:
  :show-inheritance:
  :special-members:
  :exclude-members: 

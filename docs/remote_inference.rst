.. _remote_inference:

Remote Inference
================

Remote inference allows you to run surveys at the Expected Parrot server instead of your own machine.


How it works 
------------

When remote inference is activated, calling the `run()` method on a survey will send it to the Expected Parrot server.
Survey results and job details (job history, costs, etc.) are automatically stored remotely at the server and are accessible from your workspace or at the Coop web app.
By default, if any questions have been run remotely before, the responses are retrieved from the universal remote cache instead of running the questions again.
Any new responses are automatically added to the universal remote cache and become available to you and other users to retrieve in the future.
If you want fresh responses you can turn off remote caching for a particular job by passing `remote_cache=False` or a `Cache` object to the `run()` method.
Learn more about remote caching features at the :ref:`remote_cache` section.

You can use remote inference with your own keys for language models or your Expected Parrot API key.
Running surveys with your Expected Parrot API keys requires credits to cover API calls to service providers.
You can check your balance and purchase credits at the `Credits <https://www.expectedparrot.com/home/credits>`_ page of your account.
You do not need to purchase credits to run jobs with your own keys.
Learn more about purchasing credits and calculating costs at the :ref:`credits` section.

*Note:* You must have a Coop account in order to use remote inference and caching.
By using remote inference you agree to terms of use of service providers, which Expected Parrot may accept on your behalf and enforce in accordance with our `terms of use <https://www.expectedparrot.com/terms>`_.


Activating remote inference
---------------------------

Log into your `Coop account <https://www.expectedparrot.com/login>`_ and navigate to your `Settings <a href="https://www.expectedparrot.com/home/settings>`_ page.
Toggle on the slider for *Remote inference*:

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


Using remote inference
----------------------

With remote inference activated, calling the `run()` method will send a survey to the Expected Parrot server and allow you to access results and all information about it (job history, costs, etc.) from your workspace or the Coop web app.
You can optionally pass a `remote_inference_description` to identify the job at Coop and a visibility setting `remote_inference_visibility` ("private" or "public"; the default setting for all objects is "unlisted").
These can be edited at any time from your workspace or at the Coop web app.

For example, here we run a simple survey with remote inference activated, and pass a description and visibility to readily identify the job at Coop:

.. code-block:: python

  from edsl import Model, QuestionFreeText, Survey

  m = Model("gemini-1.5-flash")

  q = QuestionFreeText(
    question_name = "prime",
    question_text = "Is 2 a prime number?"
  )

  survey = Survey(questions = [q])

  results = survey.by(m).run(remote_inference_description="Example survey", remote_inference_visibility="public")


Output (details will be unique to your job):

.. code-block:: text

  ✓ Current Status: Job completed and Results stored on Coop: http://localhost:1234/content/cfc51a12-63fe-41cf-b441-66d78ba47fb0


Results are automatically stored at the Expected Parrot server.
You can access them from your workspace or at the `Remote cache <https://www.expectedparrot.com/home/remote-cache>`_ page of your account.


Viewing jobs & results
----------------------

Navigate to the `Remote inference <https://www.expectedparrot.com/home/remote-inference>`_ page of your account to view the status of your job and the results.
Once your job has finished, it will appear with a status of *Completed*:

.. image:: static/remote_inference_job_completed_new.png
  :alt: Remote inference page on the Coop web app. There is one job shown, and it has a status of "Completed."
  :align: center
  :width: 650px

.. raw:: html

  <br>


You can then select **View all** to access the results of the job.
The results are provided as an EDSL object for you to view, pull and share with others:

.. image:: static/remote_inference_results_new.png
  :alt: Remote inference results page on the Coop web app. There is one result shown.
  :align: center
  :width: 650px

.. raw:: html

  <br>


Job details and costs 
---------------------

When you run a job using your Expected Parrot API key you are charged credits based on the number of tokens used. 
(When you run a job using your own keys you are charged directly by service providers based on the terms of your accounts.)

Before running a job, you can estimate the cost of the job by calling the `estimate_job_cost()` method on the `Job` object (a survey combined with a model).
This will return information about the estimated total cost, input tokens, output tokens, and per-model costs:

For example, here we estimate the cost of running the example survey with a model:

.. code-block:: python

  from edsl import Survey, Model

  survey = Survey.example()
  model = Model("gpt-4o")
  job = survey.by(model)

  estimated_job_cost = job.estimate_job_cost()
  estimated_job_cost 


Output:

.. code-block:: text

  {'estimated_total_cost': 0.0018625,
   'estimated_total_input_tokens': 185,
   'estimated_total_output_tokens': 140,
   'model_costs': [{'inference_service': 'openai',
     'model': 'gpt-4o',
     'estimated_cost': 0.0018625,
     'estimated_input_tokens': 185,
     'estimated_output_tokens': 140}]}


You can also estimate the cost in credits to run the job remotely by passing the job to the `remote_inference_cost()` method of a `Coop` client object:

.. code-block:: python

  from edsl import Coop 

  coop = Coop()

  estimated_remote_inference_cost = coop.remote_inference_cost(job) # using the job object from above
  estimated_remote_inference_cost


Output:

.. code-block:: text

  {'credits': 0.19, 'usd': 0.0018625}


Details on these methods can be found in the :ref:`credits` section.

After running a job, you can view the actual cost in your job history or by calling the `remote_inference_cost()` method and passing it the job UUID
(this is distinct from the results UUID, and can be found in your job history page).

You can also check the details of a job using the `remote_inference_get()` method as pass it the job UUID.

*Note:* When you run a job using your own keys, the cost estimates are based on the prices listed in the `model pricing page <https://www.expectedparrot.com/getting-started/coop-pricing>`_.
Your actual charges from service providers may vary based on the terms of your accounts with service providers.


Job history
-----------

You can click on any job to view its history. 
When a job fails, the job history logs will describe the error that caused the failure.

.. .. image:: static/coop_remote_inference_history_failed.png
..   :alt: A screenshot of job history logs on the Coop web app. The job has failed due to insufficient funds.
..   :align: center
..   :width: 350px

.. .. raw:: html

..   <br>


Job history can also provide important information about cancellation. 
When you cancel a job, one of two things must be true:

1. **The job hasn't started running yet.** No credits will be deducted from your balance.
2. **The job has started running.** Credits will be deducted.

When a late cancellation has occurred, the credits deduction will be reflected in your job history.

.. .. image:: static/coop_remote_inference_history_cancelled.png
..   :alt: A screenshot of job history logs on the Coop web app. The job has been cancelled late, and 2 credits have been deducted from the user's balance.
..   :align: center
..   :width: 300px

.. .. raw:: html

..   <br>


Using remote cache with remote inference
----------------------------------------

When remote caching is used with remote inference, existing results are retrieved when identical questions are rerun.
If you do not specify a cache to use with a survey or turn remote caching off, the universal remote cache is made available for retrieving existing responses by default.
You can turn off remote caching for a particular job by passing `remote_cache=False` or a `Cache` object to the `run()` method to use instead.
New responses are automatically added to the universal remote cache regardless of whether you specify a cache to use for retrieving responses.


Inspecting your remote cache
----------------------------

You can view your remote cache history at the `Remote cache <https://www.expectedparrot.com/home/remote-cache>`_ page of your account.

For example, we can see that the remote cache has an entry for the job that we ran above:

.. image:: static/remote_cache_history_new.png
  :alt: Remote cache entry on the Coop web app.
  :align: center
  :width: 650px

.. raw:: html

  <br>


The details are available in the job history:

.. image:: static/remote_cache_entry_new.png
  :alt: An entry in the job history log on the Coop web app. It shows that 1 new entry was added to the remote cache during this job.
  :align: center
  :width: 650px

.. raw:: html

  <br><br>



Remote inference methods
------------------------

Coop class
^^^^^^^^^^

.. autoclass:: edsl.coop.coop.Coop
  :members: remote_inference_create, remote_inference_get, remote_inference_cost
  :undoc-members:
  :show-inheritance:
  :special-members:
  :exclude-members: 

.. _remote_inference:

Remote Inference
================

Remote inference allows you to run EDSL surveys on the Expected Parrot server with a single API key for all available language models, instead of providing your own :ref:`api_keys` to access models on your local machine.
You can also save survey results and API calls on the Expected Parrot server by activating :ref:`remote_caching`.


Activating remote inference
---------------------------

1. Create a `Coop account <https://www.expectedparrot.com/login>`_. 

2. Navigate to the `API Settings <a href="https://www.expectedparrot.com/home/api>`_ page of your account. Toggle on the slider for *Remote inference* and copy your Expected Parrot API key.

.. image:: static/coop_api_key.png
  :alt: Toggle on remote inference and copy your Expected Parrot API key
  :align: center
  :width: 100%
  

.. raw:: html

  <br><br>


You can also toggle on *Remote caching* to automatically save all of your survey results and API calls at the Expected Parrot server.
Learn more in the :ref:`remote_caching` section.

3. Add the following line to your `.env` file in your `edsl` working directory (replace `your_api_key_here` with your actual Expected Parrot API key):

.. code-block:: python

  EXPECTED_PARROT_API_KEY='your_api_key_here'


This will save your Expected Parrot API key as an environment variable that EDSL can access.
You can regenerate your key (and update your `.env` file) at any time.
Your `.env` file is also where you can store :ref:`api_keys` for language models that you use locally with EDSL.


Using remote inference
----------------------

With remote inference activated, calling the `run()` method will send a survey to the Expected Parrot server.


Estimating job costs
^^^^^^^^^^^^^^^^^^^^

Before running a job, we can estimate the cost by calling the `estimate_job_cost()` method on the job.

Example:

.. code-block:: python

  from edsl import Survey, Model

  survey = Survey.example()

  model = Model("gemini-1.5-flash")

  job = survey.by(model)

  survey.estimate_job_cost()


Output:

.. code-block:: text

  xxxxxxxxxx
  


Running a job
^^^^^^^^^^^^^

When we run the job, we can optionally pass a `remote_inference_description` string to identify it at the Coop (or edit it later).

Example:

.. code-block:: python

  from edsl import Survey, Model

  survey = Survey.example()

  model = Model("gemini-1.5-flash")

  results = survey.by(model).run(remote_inference_description="Example survey")


Output (details will be unique to your job):

.. code-block:: text

  Remote inference activated. Sending job to server...
  Job completed and Results stored on Coop (Results uuid=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx).


Viewing the results
-------------------

Navigate to the `Remote inference <https://www.expectedparrot.com/home/remote-inference>`_ section of your Coop account to view the status of your job and the results.
Once your job has finished, it will appear with a status of *Completed*:

.. image:: static/coop_remote_inference_jobs_completed.png
  :alt: Remote inference page on the Coop web app. There is one job shown, and it has a status of "Completed."
  :align: center
  :width: 650px

.. raw:: html

  <br>


You can then select **View** to access the results of the job.
Your results are provided as an EDSL object for you to view, pull and share with others. 

You can also access the results URL by calling `coop.get()` and passing the results UUID that was assigned when the job was run:

.. code-block:: python

  from edsl import Coop

  coop = Coop()

  cached_results = coop.get("xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")


We can verify that the results are the same (uncomment the line below to print the results):

.. code-block:: python

  # print(cached_results)


Job details and costs 
---------------------

When you run a job, you will be charged credits based on the number of tokens used. 
You can view the cost of a job in your job history or by calling the `remote_inference_cost()` method and passing it the job UUID 
(this is distinct from the results UUID, and can be found in your job history page).

Example:

.. code-block:: python

  job_cost = coop.remote_inference_cost("xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx") 
  job_cost 


Output:

.. code-block:: text

  2.5


You can also check the details of a job using the `remote_inference_get()` method:

Example:

.. code-block:: python

  job_details = coop.remote_inference_get("xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")
  

Output:

.. code-block:: text




Job history
-----------

You can click on any job to view its history. 
When a job fails, the job history logs will describe the error that caused the failure:

.. image:: static/coop_remote_inference_history_failed.png
  :alt: A screenshot of job history logs on the Coop web app. The job has failed due to insufficient funds.
  :align: center
  :width: 350px

.. raw:: html

  <br>


Job history can also provide important information about cancellation. 
When you cancel a job, one of two things must be true:

1. **The job hasn't started running yet.** No credits will be deducted from your balance.
2. **The job has started running.** Credits will be deducted.

When a late cancellation has occurred, the credits deduction will be reflected in your job history.

.. image:: static/coop_remote_inference_history_cancelled.png
  :alt: A screenshot of job history logs on the Coop web app. The job has been cancelled late, and 2 credits have been deducted from the user's balance.
  :align: center
  :width: 300px

.. raw:: html

  <br>


Using remote inference with remote caching
------------------------------------------

When remote caching and remote inference are both turned on, your remote jobs will use your remote cache entries when applicable.

.. image:: static/coop_toggle_remote_cache_and_inference.png
  :alt: Remote cache and remote inference toggles on the Coop web app
  :align: center
  :width: 300px

.. raw:: html

  <br>


Here we rerun the survey from above:

.. code-block:: python

  survey.run(remote_inference_description="Example survey rerun")


The remote cache now has a new entry in the remote cache logs:

.. image:: static/coop_remote_inference_cache_logs.png
  :alt: Remote cache logs on the Coop web app. There is one log that reads, "Add 1 new cache entry from remote inference job."
  :align: center
  :width: 650px

.. raw:: html

  <br>


If the remote cache has been used for a particular job, the details will also show up in job history:

.. image:: static/coop_remote_inference_history_cache.png
  :alt: An entry in the job history log on the Coop web app. It shows that 1 new entry was added to the remote cache during this job.
  :align: center
  :width: 300px

.. raw:: html

  <br>



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

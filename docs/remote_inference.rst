.. _remote_inference:

Remote Inference
================

Remote inference allows you to run EDSL surveys on the Expected Parrot server with a single API key for all available language models, instead of providing your own :ref:`api_keys` for language models to access them on your local machine.


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
(Your `.env` file is also where you can store :ref:`api_keys` for language models that you use locally with EDSL.)

When remote inference is on, surveys that you run will be sent to the Expected Parrot server for processing.


Using remote inference
----------------------

With remote inference activated, calling the `run()` method will send a survey to the Expected Parrot server.
You can optionally pass a `remote_inference_description` string to identify the job at the Coop or edit it later.

Example:

.. code-block:: python

  from edsl import Survey

  survey = Survey.example()

  results = survey.run(remote_inference_description="Example survey", verbose=True)


Output (actual details will be unique to your actual job):

.. code-block:: text

  Remote inference activated. Sending job to server...
  Remote caching activated. The remote cache will be used for this job.
  Remote inference started (Job uuid=db60986e-1628-4dad-b578-833deda382f2).
  Job completed and Results stored on Coop (Results uuid=6b7358e5-9694-4ab0-aba1-3ff2f974d062).


Viewing the results
^^^^^^^^^^^^^^^^^^^

Navigate to the `Remote inference <https://www.expectedparrot.com/home/remote-inference>`_ section of your Coop account to view the status of your job and the results:

.. image:: static/api_menu_remote_inference.png
  :alt: Coop web app menu pane. "Remote inference" option is highlighted.
  :align: center
  :width: 250px

.. raw:: html

  <br>

  
Once your job has finished, it will appear at the with a status of *Completed*:

.. image:: static/coop_remote_inference_jobs_completed.png
  :alt: Remote inference page on the Coop web app. There is one job shown, and it has a status of "Completed."
  :align: center
  :width: 650px

.. raw:: html

  <br>


You can then click on the **View** link to access the results of the job.
Your results are provided as an EDSL object for you to view, pull and share with others. 

You can also access the results URL from EDSL by calling `coop.remote_cache_get()` and passing the UUID assigned when the job was run:

.. code-block:: python

  from edsl import Coop

  coop = Coop()

  coop.remote_cache_get("1234abcd-abcd-1234-abcd-1234abcd1234")


Job history
-----------

You can click on any job to view its history. When a job fails, the job history logs
will describe the error that caused the failure:

.. image:: static/coop_remote_inference_history_failed.png
  :alt: A screenshot of job history logs on the Coop web app. The job has failed due to insufficient funds.
  :align: center
  :width: 350px

.. raw:: html

  <br>


Job history can also provide important information about cancellation. When you cancel a job, one of two things must be true:

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


Let's rerun the survey from earlier:

.. code-block:: python

  survey.run(remote_inference_description="Example survey rerun", verbose=True)


After running this survey, you will have a new entry in the remote cache.
This is reflected in your remote cache logs:

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

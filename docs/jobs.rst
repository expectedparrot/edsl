.. _jobs:

Jobs
====

A `Job` is a `Survey` object combined with one or more `Model` objects and any `Agent` and `Scenario` objects that have been added to the survey.
It is used to manage the execution of a survey with the specified models, agents and scenarios. 

A job instance can be created by adding a model to a survey with the `by()` method, or by using the `Jobs` class to create a job directly.
For example:

.. code-block:: python

   from edsl import QuestionFreeText, Survey, Model, Jobs

   q = QuestionFreeText(
      question_name = "example",
      question_text = "What is your favorite color?",
   )
   survey = Survey(questions = [q])
   model = Model("gpt-4o", service_name = "openai")
   job = survey.by(model)

   # or using the Jobs class
   job = Jobs(survey).by(model)


It can be useful to work with jobs when you want to run a survey with multiple models, agents, or scenarios, or when you want to manage the execution of a survey in a more structured way.

There are several methods available in the `Jobs` class to manage jobs, such as `by()`, `run()`, and `list()`:

* The `by()` method is used to add a model to the survey and create a job instance. 
* The `run()` method is used to execute the job.
* The `list()` method is used to list details of jobs that have been posted to Coop.
* The `fetch()` method is used to retrieve jobs that have been posted to Coop.


For example, to run the above job:

.. code-block:: python

   job.run()


To retrieve details about your 10 most recent jobs posted to Coop:

.. code-block:: python

   from edsl import Jobs

   jobs = Jobs().list()


The following information will be returned:

.. list-table::
  :header-rows: 1

  * - Column
    - Description
  * - uuid
    - The UUID of the job.
  * - description
    - A description of the job, if any.
  * - status
    - The status of the job (e.g., running, completed, failed).
  * - cost_credits
    - The cost of the job in credits.
  * - iterations
    - The number of iterations the job has run.
  * - results_uuid
    - The UUID of the results for the job.
  * - latest_error_report_uuid
    - The UUID of the latest error report for the job, if any.
  * - latest_failure_reason
    - The reason for the latest failure, if any.
  * - version
    - The EDSL version used to create the job.
  * - created_at
    - The date and time the job was created.


You can also specify the `page_size` parameter to limit the number of jobs returned, and the `page` parameter to paginate through the jobs:

.. code-block:: python

   jobs = Jobs.list(page_size=5, page=2)


You can also filter jobs by their status using the `status` parameter:

.. code-block:: python

   jobs = Jobs.list(status="running")


You can filter jobs by description using the `search_query` parameter:

.. code-block:: python

   jobs = Jobs.list(search_query="testing")


To fetch the `Jobs` objects directly you can use the `fetch()` method:

.. code-block:: python

   from edsl import Jobs 

   jobs = Jobs.list(page_size=1).fetch()


Or to fetch the associated results:

.. code-block:: python

   from edsl import Jobs 

   jobs = Jobs.list(page_size=1).fetch_results()



Prompts 
-------

It can also be useful to work with `Jobs` objects in order to inspect user and system prompts before running the job.

For example, here we create a survey and use the job to inspect the prompts:

.. code-block:: python

   from edsl import QuestionFreeText, Survey, Agent, Model, Jobs

   q = QuestionFreeText(
   question_name = "example",
   question_text = "What is your favorite color?",
   )

   survey = Survey(questions = [q])

   agent = Agent(traits = {"persona":"You are an artist."})

   model = Model("gpt-4o", service_name = "openai")

   job = survey.by(agent).by(model)

   # Inspect the prompts
   job.show_prompts()


This will return the following information:

.. list-table::
  :header-rows: 1

  * - user_prompt	
    - What is your favorite color?
  * - system_prompt	
    - You are answering questions as if you were a human. Do not break character.Your traits: {'persona': 'You are an artist.'}	
  * - interview_index	
    - 0	
  * - question_name	
    - example	
  * - scenario_index	
    - 0
  * - agent_index	
    - 0
  * - model	
    - gpt-4o
  * - estimated_cost	
    - 0.000373
  * - cache_keys
    - ['e549b646508cfd459f88379649ebe8ba']



Jobs class
----------
.. autoclass:: edsl.jobs.Jobs
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__

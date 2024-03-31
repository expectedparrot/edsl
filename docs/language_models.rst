.. _language_models:

Language Models
===============
Language models are used to simulate agent responses to questions and can be specified when running a job.

Available models
----------------
We can see all of the available models by calling the `available()` method on the `Model` class:

.. code-block:: python

   from edsl import Model

   Model.available()

This will return a list of short names for available models to choose from:

.. code-block:: python

   ['gpt-3.5-turbo',
   'gpt-4-1106-preview',
   'gemini_pro',
   'llama-2-13b-chat-hf',
   'llama-2-70b-chat-hf',
   'mixtral-8x7B-instruct-v0.1']

Specifying a model
------------------
We specify a model for a job by creating a `Model` object for an available model and optionally setting model parameters. 
For example, the following code creates a `Model` object for the GPT 4 model with default model parameters:

.. code-block:: python

   from edsl import Model

   model = Model('gpt-4-1106-preview')

We can inspect the default modifiable parameters of the model by calling the `parameters` method on it:

.. code-block:: python

   models.parameters

This will return the following dictionary of parameters:

.. code-block:: python

   {'temperature': 0.5,
   'max_tokens': 1000,
   'top_p': 1,
   'frequency_penalty': 0,
   'presence_penalty': 0,
   'use_cache': True}

Adding a model to a job
-----------------------
Similar to other job components (agents and scenarios), we can add a model to a job by appending it to the job with the `by()` method when the job is run.
If multiple models are specified, they are added as a list in the `by()` method.
For example, the following code specifies that a job should be run with each of GPT 4 and Llama 2:

.. code-block:: python

   models = [Model('gpt-4-1106-preview'), Model('llama-2-70b-chat-hf')]

   results = survey.by(models).run()

This will generate a result for each question/agent pair with each of the models.

Default model
-------------
If no model is specified, a job is automatically run with the default model (GPT 4).
For example, the following code runs a job with the default model (and no agents or scenarios) without needing to import the `Model` class:

.. code-block:: python

   results = survey.run()

Inspecting model details in results
-----------------------------------
The model used for each result can be inspected by calling the `model` attribute for the result object.
For example, the following code prints the model and model parameters used for the first result:

.. code-block:: python

   results[0]["model"]

This will return the default model name and parameters if no model was specified:

.. code-block:: python

   LanguageModelOpenAIFour(
      model = 'gpt-4-1106-preview', 
      parameters={'temperature': 0.5, 'max_tokens': 1000, 'top_p': 1, 'frequency_penalty': 0, 'presence_penalty': 0, 'use_cache': True}
      )

If multiple models were used to generate results, we can print the attributes in a table.
For example, tablehe following code prints a table of the model names and temperatures for some results:

.. code-block:: python

   from edsl import Model

   models = [Model('gpt-4-1106-preview'), Model('llama-2-70b-chat-hf')]

   from edsl.questions import QuestionMultipleChoice, QuestionFreeText

   q1 = QuestionMultipleChoice(
      question_name = "favorite_day",
      question_text = "What is your favorite day of the week?",
      question_options = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
   )

   q2 = QuestionFreeText(
      question_name = "favorite_color",
      question_text = "What is your favorite color?"
   )

   from edsl import Survey 

   survey = Survey([q1, q2])

   results = survey.by(models).run()

   results.select("model.model", "model.temperature").print()

The table will look like this:

.. list-table::
   :widths: 10 10 
   :header-rows: 1

   * - model.model
     - model.temperature
   * - gpt-4-1106-preview
     - 0.5
   * - llama-2-70b-chat-hf
     - 0.5

We can also print model attributes together with other result attributes.
We can see a list of all results attributes by calling the `columns` method on the results object:

.. code-block:: python

   results.columns

For the above example, this will display the following list of attributes (note that no agents were specified, so there are no agent fields listed other than the default `agent_name` that is generated when a job is run):

.. code-block:: python

   ['agent.agent_name',
   'answer.favorite_color',
   'answer.favorite_day',
   'answer.favorite_day_comment',
   'model.frequency_penalty',
   'model.max_new_tokens',
   'model.max_tokens',
   'model.model',
   'model.presence_penalty',
   'model.stopSequences',
   'model.temperature',
   'model.top_k',
   'model.top_p',
   'model.use_cache',
   'prompt.favorite_color_system_prompt',
   'prompt.favorite_color_user_prompt',
   'prompt.favorite_day_system_prompt',
   'prompt.favorite_day_user_prompt',
   'raw_model_response.favorite_color_raw_model_response',
   'raw_model_response.favorite_day_raw_model_response']

The following code will display a table of the model names together with the simulated answers:

.. code-block:: python

   (results
   .select("model.model", "answer.favorite_day", "answer.favorite_color")
   .print()
   )

The table will look like this:

.. list-table::
   :widths: 30 40 40
   :header-rows: 1

   * - model.model
     - answer.favorite_day
     - answer.favorite_color
   * - gpt-4-1106-preview
     - Sat
     - My favorite color is blue. 
   * - llama-2-70b-chat-hf
     - Sat
     - My favorite color is blue. It reminds me of the ocean on a clear summer day, full of possibilities and mystery.

To explore more methods of inspecting and printing results, see the :ref:`results` documentation.


LanguageModel class
-------------------

.. automodule:: edsl.language_models.LanguageModel
   :members:
   :undoc-members:
   :show-inheritance:


Other methods
-------------

.. automodule:: edsl.language_models.model_interfaces
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: edsl.language_models.registry
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: edsl.language_models.repair
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: edsl.language_models.schemas
   :members:
   :undoc-members:
   :show-inheritance:
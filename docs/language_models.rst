.. _language_models:

Language Models
===============
Language models are used to generate agent responses to questions and can be specified when running a survey.
API keys are required in order to access the available models, and should be stored in your private `.env` file.
See the :ref:`starter_tutorial` section for instructions on storing your keys.

Available models
----------------
We can see all of the currently available models by calling the `available()` method on the `Model` class:

.. code-block:: python

   from edsl import Model

   Model.available()

This will return a list of names for available models to choose from:

.. code-block:: python

   ['claude-3-haiku-20240307', 
    'claude-3-opus-20240229', 
    'claude-3-sonnet-20240229', 
    'dbrx-instruct', 
    'gpt-3.5-turbo',
    'gpt-4-1106-preview',
    'gemini_pro',
    'llama-2-13b-chat-hf',
    'llama-2-70b-chat-hf',
    'mixtral-8x7B-instruct-v0.1']

The available models are updated regularly.
A current list is also available at :py:class:`edsl.enums.LanguageModelEnum`.

*If you don't see a model that you want to work with, please send us a feature request to add it!*

Specifying a model
------------------
We specify a model by creating a `Model` object and passing it the name of an available model.
We can optionally set the other model parameters as well (temperature, etc.). 
For example, the following code creates a `Model` object for Claude 3 with default model parameters:

.. code-block:: python

   from edsl import Model

   m = Model('claude-3-opus-20240229')

We can see that the object consists of a model name and a dictionary of parameters:

.. code-block:: python

   m

This will return the following:

.. code-block:: python

   ClaudeOpus(
      model = 'claude-3-opus-20240229', 
      parameters={'temperature': 0.5, 'max_tokens': 1000, 'top_p': 1, 'frequency_penalty': 0, 'presence_penalty': 0, 'logprobs': False, 'top_logprobs': 3}
   )

We can also print the model name and parameters in a readable table with the `print()` method:

.. code-block:: python

   m.print()

This will print the following table:

.. code-block:: python

                                       Language Model                                       
   ┏━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ Attribute         ┃ Value                                                               ┃
   ┡━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ model             │ 'claude-3-opus-20240229'                                            │
   │ parameters        │ {'temperature': 0.5, 'max_tokens': 1000, 'top_p': 1,                │
   │                   │ 'frequency_penalty': 0, 'presence_penalty': 0, 'logprobs': False,   │
   │                   │ 'top_logprobs': 3}                                                  │
   │ temperature       │ 0.5                                                                 │
   │ max_tokens        │ 1000                                                                │
   │ top_p             │ 1                                                                   │
   │ frequency_penalty │ 0                                                                   │
   │ presence_penalty  │ 0                                                                   │
   │ logprobs          │ False                                                               │
   │ top_logprobs      │ 3                                                                   │
   └───────────────────┴─────────────────────────────────────────────────────────────────────┘

We can also inspect the default parameters of the model by calling the `parameters` method on it:

.. code-block:: python

   m.parameters

This will return the following dictionary of parameters:

.. code-block:: python

   {'temperature': 0.5, 
   'max_tokens': 1000, 
   'top_p': 1, 
   'frequency_penalty': 0, 
   'presence_penalty': 0, 
   'logprobs': False, 
   'top_logprobs': 3}


Running a survey with a model
-----------------------------
Similar to how we specify :ref:`agents` and :ref:`scenarios` in running a survey, we specify the models to use by appending them with the `by()` method when the survey is run.
If a single model is specified, it is the only item passed to the `by()` method. 
If multiple models are to be used, they are passed as a list.
For example, the following code specifies that a survey should be run with each of GPT 4 and Llama 2:

.. code-block:: python

   from edsl import Model

   models = [Model('gpt-4-1106-preview'), Model('llama-2-70b-chat-hf')]

   from edsl import Survey 

   survey = Survey.example()

   results = survey.by(models).run()

This will generate a result for each question in the survey with each model.
If agents and/or scenarios are also specified, the responses will be generated for each combination of agents, scenarios and models.
Each component is added with its own `by()` method, the order of which does not matter.
The following commands are equivalent:

.. code-block:: python

   results = survey.by(scenarios).by(agents).by(models).run()

   results = survey.by(models).by(agents).by(scenarios).run()

If we only want to use a single model it can be passed directly to the `by()` method:

.. code-block:: python

   results = survey.by(Model('gpt-4-1106-preview')).run()

Default model
-------------
If no model is specified, a survey is automatically run with the default model (GPT 4).
For example, the following code runs a survey with the default model (and no agents or scenarios) without needing to import the `Model` class:

.. code-block:: python

   from edsl import Survey

   results = survey.run()

Inspecting model details in results
-----------------------------------
After running a survey, we can inspect the models used by calling the `models` method on the result object.
For example, we can verify the default model when running a survey without specifying a model:

.. code-block:: python

   from edsl import Survey

   survey = Survey.example()

   results = survey.run()

   results.models

This will return the following:

.. code-block:: python

   [LanguageModelOpenAIFour(
      model = 'gpt-4-1106-preview', 
      parameters={'temperature': 0.5, 'max_tokens': 1000, 'top_p': 1, 'frequency_penalty': 0, 'presence_penalty': 0, 'logprobs': False, 'top_logprobs': 3}
   )]

To learn more about all the components of a `Results` object, please see the :ref:`results` section.

Printing model attributes
-------------------------
If multiple models were used to generate results, we can print the attributes in a table.
For example, the following code prints a table of the model names and temperatures for some results:

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
   'iteration.iteration', 
   'model.frequency_penalty', 
   'model.logprobs', 
   'model.max_new_tokens', 
   'model.max_tokens', 
   'model.model', 
   'model.presence_penalty', 
   'model.stopSequences', 
   'model.temperature', 
   'model.top_k', 
   'model.top_logprobs', 
   'model.top_p', 
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

To learn more about methods of inspecting and printing results, please see the :ref:`results` section.
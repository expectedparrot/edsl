.. _language_models:

Language Models
===============
Language models are used to generate agent responses to questions and can be specified when running a survey.
API keys are required in order to access the available models, and should be stored in your private `.env` file.
See the :ref:`api_keys` page for instructions on storing your API keys.

Available services 
------------------
We can see all of the available services by calling the `services()` method of the `Model` class:

.. code-block:: python

   from edsl import Model

   Model.services()


This will return a list of the services we can choose from:

.. code-block:: python

   ['openai', 'anthropic', 'deep_infra', 'google']


Available models
----------------
We can see all of the available models by calling the `available()` method of the `Model` class:

.. code-block:: python

   from edsl import Model

   Model.available()


This will return a list of the models we can choose from:

.. code-block:: python

   [['01-ai/Yi-34B-Chat', 'deep_infra', 0],
   ['Austism/chronos-hermes-13b-v2', 'deep_infra', 1],
   ['Gryphe/MythoMax-L2-13b', 'deep_infra', 2],
   ['Gryphe/MythoMax-L2-13b-turbo', 'deep_infra', 3],
   ['HuggingFaceH4/zephyr-orpo-141b-A35b-v0.1', 'deep_infra', 4],
   ['Phind/Phind-CodeLlama-34B-v2', 'deep_infra', 5],
   ['Qwen/Qwen2-72B-Instruct', 'deep_infra', 6],
   ['Qwen/Qwen2-7B-Instruct', 'deep_infra', 7],
   ['bigcode/starcoder2-15b', 'deep_infra', 8],
   ['bigcode/starcoder2-15b-instruct-v0.1', 'deep_infra', 9],
   ['claude-3-5-sonnet-20240620', 'anthropic', 10],
   ['claude-3-haiku-20240307', 'anthropic', 11],
   ['claude-3-opus-20240229', 'anthropic', 12],
   ['claude-3-sonnet-20240229', 'anthropic', 13],
   ['codellama/CodeLlama-34b-Instruct-hf', 'deep_infra', 14],
   ['codellama/CodeLlama-70b-Instruct-hf', 'deep_infra', 15],
   ['cognitivecomputations/dolphin-2.6-mixtral-8x7b', 'deep_infra', 16],
   ['databricks/dbrx-instruct', 'deep_infra', 17],
   ['deepinfra/airoboros-70b', 'deep_infra', 18],
   ['gemini-pro', 'google', 19],
   ['google/codegemma-7b-it', 'deep_infra', 20],
   ['google/gemma-1.1-7b-it', 'deep_infra', 21],
   ['gpt-3.5-turbo', 'openai', 22],
   ['gpt-3.5-turbo-0125', 'openai', 23],
   ['gpt-3.5-turbo-0301', 'openai', 24],
   ['gpt-3.5-turbo-0613', 'openai', 25],
   ['gpt-3.5-turbo-1106', 'openai', 26],
   ['gpt-3.5-turbo-16k', 'openai', 27],
   ['gpt-3.5-turbo-16k-0613', 'openai', 28],
   ['gpt-3.5-turbo-instruct', 'openai', 29],
   ['gpt-3.5-turbo-instruct-0914', 'openai', 30],
   ['gpt-4', 'openai', 31],
   ['gpt-4-0125-preview', 'openai', 32],
   ['gpt-4-0613', 'openai', 33],
   ['gpt-4-1106-preview', 'openai', 34],
   ['gpt-4-1106-vision-preview', 'openai', 35],
   ['gpt-4-turbo', 'openai', 36],
   ['gpt-4-turbo-2024-04-09', 'openai', 37],
   ['gpt-4-turbo-preview', 'openai', 38],
   ['gpt-4-vision-preview', 'openai', 39],
   ['gpt-4o', 'openai', 40],
   ['gpt-4o-2024-05-13', 'openai', 41],
   ['lizpreciatior/lzlv_70b_fp16_hf', 'deep_infra', 42],
   ['llava-hf/llava-1.5-7b-hf', 'deep_infra', 43],
   ['meta-llama/Llama-2-13b-chat-hf', 'deep_infra', 44],
   ['meta-llama/Llama-2-70b-chat-hf', 'deep_infra', 45],
   ['meta-llama/Llama-2-7b-chat-hf', 'deep_infra', 46],
   ['meta-llama/Meta-Llama-3-70B-Instruct', 'deep_infra', 47],
   ['meta-llama/Meta-Llama-3-8B-Instruct', 'deep_infra', 48],
   ['microsoft/Phi-3-medium-4k-instruct', 'deep_infra', 49],
   ['microsoft/WizardLM-2-7B', 'deep_infra', 50],
   ['microsoft/WizardLM-2-8x22B', 'deep_infra', 51],
   ['mistralai/Mistral-7B-Instruct-v0.1', 'deep_infra', 52],
   ['mistralai/Mistral-7B-Instruct-v0.2', 'deep_infra', 53],
   ['mistralai/Mistral-7B-Instruct-v0.3', 'deep_infra', 54],
   ['mistralai/Mixtral-8x22B-Instruct-v0.1', 'deep_infra', 55],
   ['mistralai/Mixtral-8x22B-v0.1', 'deep_infra', 56],
   ['mistralai/Mixtral-8x7B-Instruct-v0.1', 'deep_infra', 57],
   ['nvidia/Nemotron-4-340B-Instruct', 'deep_infra', 58],
   ['openchat/openchat-3.6-8b', 'deep_infra', 59],
   ['openchat/openchat_3.5', 'deep_infra', 60]]


Adding a model
--------------
Available models are added automatically.
A current list is also viewable at :py:class:`edsl.enums.LanguageModelType`.
If you do not see a publicly available model that you want to work with, please send us a feature request to add it or add it yourself by calling the `add_model()` method:

.. code-block:: python

   from edsl import Model

   Model.add_model(service_name = "anthropic", model_name = "new_model")

This will add the model `new_model` to the `anthropic` service.
You can then see the model in the list of available models, and search by service name:

.. code-block:: python

   Model.available("anthropic")


Output:

.. code-block:: python

[['claude-3-5-sonnet-20240620', 'anthropic', 10],
 ['claude-3-haiku-20240307', 'anthropic', 11],
 ['claude-3-opus-20240229', 'anthropic', 12],
 ['claude-3-sonnet-20240229', 'anthropic', 13],
 ['new_model', 'anthropic', 61]]


Check models 
------------
We can check the models that for which we have already properly stored API keys by calling the `check_models()` method:

.. code-block:: python

   Model.check_models()

This will return a list of the available models and a confirmation message whether a valid key exists.


Specifying a model
------------------
We specify a model to use with a survey by creating a `Model` object and passing it the name of an available model.
We can optionally set other model parameters as well (temperature, etc.). 
For example, the following code creates a `Model` object for Claude 3.5 Sonnet with default model parameters:

.. code-block:: python

   from edsl import Model

   model = Model('claude-3-5-sonnet-20240620')


We can see that the object consists of a model name and a dictionary of parameters:

.. code-block:: python

   model


This will show the default parameters of the model:

.. code-block:: python

   {
      "model": "claude-3-5-sonnet-20240620",
      "parameters": {
         "temperature": 0.5,
         "max_tokens": 1000,
         "top_p": 1,
         "frequency_penalty": 0,
         "presence_penalty": 0,
         "logprobs": false,
         "top_logprobs": 3
      }
   }


Running a survey with a model
-----------------------------
Similar to how we specify :ref:`agents` and :ref:`scenarios` in running a survey, we specify the models to use by adding them to a survey with the `by()` method when the survey is run.
If a single model is specified, it is the only item passed to the `by()` method. 
If multiple models are to be used, they are passed as a list.
For example, the following code specifies that a survey be run with each of GPT 4 and Llama 2:

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


This will return the following information about the default model that was used:

.. code-block:: python

   {
      "model": "gpt-4-1106-preview",
      "parameters": {
         "temperature": 0.5,
         "max_tokens": 1000,
         "top_p": 1,
         "frequency_penalty": 0,
         "presence_penalty": 0,
         "logprobs": false,
         "top_logprobs": 3
      }
   }

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

We can also print model attributes together with other components of results.
We can see a list of all components by calling the `columns` method on the results:

.. code-block:: python

   results.columns

For the above example, this will display the following list of components (note that no agents were specified, so there are no agent fields listed other than the default `agent_name` that is generated when a job is run):

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


LanguageModel class
-------------------

.. automodule:: edsl.language_models.LanguageModel
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: 


Other methods
-------------

.. automodule:: edsl.language_models.registry
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: 

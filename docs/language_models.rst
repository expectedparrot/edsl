.. _language_models:

Language Models
===============

Language models are used to generate agent responses to questions and can be specified when running a survey.
API keys are required in order to access the available models, and should be stored in your private `.env` file.
See the :ref:`api_keys` page for instructions on storing your API keys.


Available services 
------------------

We can see all of the available services (model providers) by calling the `services()` method of the `Model` class:

.. code-block:: python

   from edsl import Model

   Model.services()


This will return a list of the services we can choose from:

.. code-block:: python

   ['openai',
   'anthropic',
   'deep_infra',
   'google',
   'groq',
   'bedrock',
   'azure',
   'ollama',
   'test',
   'mistral']


Available models
----------------

We can see all of the available models by calling the `available()` method of the `Model` class:

.. code-block:: python

   from edsl import Model

   Model.available()


This will return a list of the models we can choose from (not shown below--run the code on yor own to see an up-to-date list).


Adding a model
--------------

Newly available models for these services are added automatically.
If you do not see a publicly available model that you want to work with, please send us a feature request to add it or add it yourself by calling the `add_model()` method:

.. code-block:: python

   from edsl import Model

   Model.add_model(service_name = "anthropic", model_name = "new_model")


This will add the model `new_model` to the `anthropic` service.
You can then see the model in the list of available models, and search by service name:

.. code-block:: python

   Model.available("anthropic")



Check models 
------------

Check the models for which you have already properly stored API keys by calling the `check_models()` method:

.. code-block:: python

   Model.check_models()


This will return a list of the available models and a confirmation message whether a valid key exists.
The output will look like this (note that the keys are not shown):

.. code-block:: text

   Checking all available models...

   Now checking: <model name>
   OK!


Etc.


Specifying a model
------------------

We specify a model to use with a survey by creating a `Model` object and passing it the name of an available model.
We can optionally set other model parameters as well (temperature, etc.). 
For example, the following code creates a `Model` object for Claude 3.5 Sonnet with default model parameters:

.. code-block:: python

   from edsl import Model

   model = Model('gpt-4o')


We can see that the object consists of a model name and a dictionary of parameters:

.. code-block:: python

   model


This will show the default parameters of the model:

.. code-block:: python

   {
      "model": "gpt-4o",
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


Running a survey with models
----------------------------
Similar to how we specify :ref:`agents` and :ref:`scenarios` in running a survey, we specify the models to use by adding them to a survey with the `by()` method when the survey is run.
We can pass either a single `Model` object or a list of models to the `by()` method. 
If multiple models are to be used they are passed as a list or as a `ModelList` object.
For example, the following code specifies that a survey be run with each of GPT 4 and Gemini Pro:

.. code-block:: python

   from edsl import Model, Survey

   models = [Model('gpt-4o'), Model('gemini-pro')]

   survey = Survey.example()

   results = survey.by(models).run()


This code uses `ModelList` instead of a list of `Model` objects:

.. code-block:: python

   from edsl import Model, ModelList, Survey

   models = ModelList(Model(m) for m in ['gpt-4o', 'gemini-pro'])

   survey = Survey.example()

   results = survey.by(models).run()


This will generate a result for each question in the survey with each model.
If agents and/or scenarios are also specified, the responses will be generated for each combination of agents, scenarios and models.
Each component is added with its own `by()` method, the order of which does not matter.
The following commands are equivalent:

.. code-block:: python

   results = survey.by(scenarios).by(agents).by(models).run()

   results = survey.by(models).by(agents).by(scenarios).run()



Default model
-------------

If no model is specified, a survey is automatically run with the default model. 
Run `Model()` to check the current default model.
For example, the following code runs the example survey with the default model (and no agents or scenarios) without needing to import the `Model` class:

.. code-block:: python

   from edsl import Survey

   results = Survey.example().run()


Inspecting model details in results
-----------------------------------

If a survey has been run, we can inspect the models that were used by calling the `models` method on the `Results` object.
For example, we can verify the default model when running a survey without specifying a model:

.. code-block:: python

   from edsl import Survey

   survey = Survey.example()

   results = survey.run()

   results.models


This will return the following information about the default model that was used (note the default model may have changed since this page was last updated):

.. code-block:: text

   [Model(model_name = 'gpt-4o', temperature = 0.5, max_tokens = 1000, top_p = 1, frequency_penalty = 0, presence_penalty = 0, logprobs = False, top_logprobs = 3)]  


To learn more about all the components of a `Results` object, please see the :ref:`results` section.


Printing model attributes
-------------------------

If multiple models were used to generate results, we can print the attributes in a table.
For example, the following code prints a table of the model names and temperatures for some results:

.. code-block:: python

   from edsl import Survey, ModelList, Model

   models = ModelList(
      Model(m) for m in ['gpt-4o', 'gemini-1.5-pro']
   )

   survey = Survey.example()

   results = survey.by(models).run()

   results.select("model", "temperature").print() # This is equivalent to: results.select("model.model", "model.temperature").print()


Output:

.. code-block:: text 

   model.model	      model.temperature
   gpt-4o	         0.5
   gemini-1.5-pro	   0.5


We can also print model attributes together with other components of results.
We can see a list of all components by calling the `columns` method on the results:

.. code-block:: python

   results.columns


Output:

.. code-block:: python

   ['agent.agent_instruction',
   'agent.agent_name',
   'answer.q0',
   'answer.q1',
   'answer.q2',
   'comment.q0_comment',
   'comment.q1_comment',
   'comment.q2_comment',
   'generated_tokens.q0_generated_tokens',
   'generated_tokens.q1_generated_tokens',
   'generated_tokens.q2_generated_tokens',
   'iteration.iteration',
   'model.frequency_penalty',
   'model.logprobs',
   'model.maxOutputTokens',
   'model.max_tokens',
   'model.model',
   'model.presence_penalty',
   'model.stopSequences',
   'model.temperature',
   'model.topK',
   'model.topP',
   'model.top_logprobs',
   'model.top_p',
   'prompt.q0_system_prompt',
   'prompt.q0_user_prompt',
   'prompt.q1_system_prompt',
   'prompt.q1_user_prompt',
   'prompt.q2_system_prompt',
   'prompt.q2_user_prompt',
   'question_options.q0_question_options',
   'question_options.q1_question_options',
   'question_options.q2_question_options',
   'question_text.q0_question_text',
   'question_text.q1_question_text',
   'question_text.q2_question_text',
   'question_type.q0_question_type',
   'question_type.q1_question_type',
   'question_type.q2_question_type',
   'raw_model_response.q0_cost',
   'raw_model_response.q0_one_usd_buys',
   'raw_model_response.q0_raw_model_response',
   'raw_model_response.q1_cost',
   'raw_model_response.q1_one_usd_buys',
   'raw_model_response.q1_raw_model_response',
   'raw_model_response.q2_cost',
   'raw_model_response.q2_one_usd_buys',
   'raw_model_response.q2_raw_model_response']

The following code will display a table of the model names together with the simulated answers:

.. code-block:: python

   (
      results
      .select("model", "answer.*")
      .print(format="rich")
   )

Output:

.. code-block:: text 

   ┏━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━┓
   ┃ model          ┃ answer ┃ answer ┃ answer ┃
   ┃ .model         ┃ .q2    ┃ .q1    ┃ .q0    ┃
   ┡━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━┩
   │ gpt-4o         │ other  │ None   │ yes    │
   ├────────────────┼────────┼────────┼────────┤
   │ gemini-1.5-pro │ other  │ other  │ no     │
   └────────────────┴────────┴────────┴────────┘


To learn more about methods of inspecting and printing results, please see the :ref:`results` section.


ModelList class
---------------

.. automodule:: edsl.language_models.ModelList
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members:


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

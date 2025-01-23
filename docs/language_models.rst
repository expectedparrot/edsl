.. _language_models:

Language Models
===============

Language models are used to generate agents' responses to survey questions and can be specified using the `Model` and `ModelList` classes.

EDSL works with a variety of different popular inference service providers, including Anthropic, Google, OpenAI and others.
Current information about available models can be found at the Expected Parrot model pricing page: https://www.expectedparrot.com/getting-started/coop-pricing.
We also recommend checking providers' websites for the most up-to-date information on available models.
It is important to check that the models you want to use are available and working as expected before running a survey.
If you need assistance checking whether a model is working, please send a message to info@expectedparrot.com or post a message at our `Discord channel <https://discord.com/invite/mxAYkjfy9m>`_.


API keys 
--------

In order to use a model, you need to have an API key for the relevant service provider.
EDSL allows you to choose whether to provide your own API keys for models or use an Expected Parrot API key to access all available models at once.
See the :ref:`api_keys` page for instructions on storing API keys.


Available services 
------------------

The following code will return a table of currently available inference services (model providers) together with an indicator whether a local key is currently stored for each service:

.. code-block:: python

   from edsl import Model

   Model.services()


Output:

.. list-table::
   :header-rows: 1

   * - Service Name
   * - openai
   * - anthropic
   * - deep_infra
   * - deepseek
   * - google
   * - groq
   * - bedrock
   * - azure
   * - ollama
   * - test
   * - together
   * - perplexity
   * - mistral


Available models
----------------

The following code will return a table of all the available models for all services (output omitted here for brevity):

.. code-block:: python

   from edsl import Model

   Model.available()


To see a list of all models for a specific service, pass the service name as an argument:

.. code-block:: python

   Model.available(service = "google")


Output:

.. list-table::
   :header-rows: 1

   * - Model Name
     - gemmini-1.0-pro
     - gemmini-1.0-flash
     - gemmini-1.5-pro
     - gemmini-pro
   * - Service Name
     - google
     - google
     - google
     - google


Adding a model
--------------

Newly available models for these services are added automatically.
If you do not see a publicly available model that you want to work with, please send us a feature request to add it or add it yourself by calling the `add_model()` method:

.. code-block:: python

   from edsl import Model

   Model.add_model(service_name = "google", model_name = "new_model")


This will add the model `new_model` to the `google` service.
You can then see the model in the list of available models, and search by service name:

.. code-block:: python

   Model.available(service = "google")


Output:

.. list-table::
   :header-rows: 1

   * - Model Name
     - gemmini-1.0-pro
     - gemmini-1.0-flash
     - gemmini-1.5-pro
     - gemmini-pro
     - new_model
   * - Service Name
     - google
     - google
     - google
     - google
     - google


Check models 
------------

The following code checks for models where API keys have been stored locally:

.. code-block:: python

   from edsl import Model
   
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
For example, the following code creates a `Model` object for `gpt-4o` with default model parameters:

.. code-block:: python

   from edsl import Model

   m = Model('gpt-4o')
   m


Output: 

.. list-table::
   :header-rows: 1

   * - key
     - value 
   * - model
     - gpt-4o
   * - parameters:temperature
     - 0.5
   * - parameters:max_tokens
     - 1000
   * - parameters:top_p
     - 1
   * - parameters:frequency_penalty
     - 0
   * - parameters:presence_penalty
     - 0
   * - parameters:logprobs
     - False
   * - parameters:top_logprobs
     - 3
   * - inference_service
     - openai


We can see that the object consists of a model name and a dictionary of the default parameters of the model, together with the name of the inference service (some models are made provided by multiple services).


Creating a list of models
-------------------------

We can create a list of models by passing a list of model names to the `ModelList` class.
For example, the following code creates a `ModelList` object for `gpt-4o` and `gemini-pro`:

.. code-block:: python

   from edsl import Model, ModelList

   ml = ModelList([Model('gpt-4o'), Model('gemini-pro')])


We can also create a model list from a list of model names:

.. code-block:: python

   from edsl import Model, ModelList

   model_names = ['gpt-4o', 'gemini-pro']

   ml = ModelList.from_names(model_names)

   ml


Output:

.. list-table::
   :header-rows: 1

   * - topP	
     - topK	
     - presence_penalty	
     - top_logprobs	
     - top_p	
     - max_tokens	
     - maxOutputTokens	
     - temperature	
     - model	
     - stopSequences	
     - logprobs	
     - frequency_penalty
   * - nan	
     - nan	
     - 0.000000	
     - 3.000000	
     - 1.000000	
     - 1000.000000	
     - nan	
     - 0.500000	
     - gpt-4o	
     - nan	
     - False	
     - 0.000000
   * - 1.000000	
     - 1.000000	
     - nan	
     - nan	
     - nan	
     - nan	
     - 2048.000000	
     - 0.500000	
     - gemini-pro	
     - []	
     - nan	
     - nan


Running a survey with models
----------------------------

Similar to how we specify :ref:`agents` and :ref:`scenarios` to use with a survey, we specify the models to use by adding them to a survey with the `by()` method when the survey is run.
We can pass either a single `Model` object or a list of models to the `by()` method. 
If multiple models are to be used they are passed as a list or as a `ModelList` object.
For example, the following code specifies that a survey will be run with each of `gpt-4o` and `gemini-1.5-flash`:

.. code-block:: python

   from edsl import Model, Survey

   models = [Model('gpt-4o'), Model('gemini-1.5-flash')]

   survey = Survey.example()

   results = survey.by(models).run()


This code uses `ModelList` instead of a list of `Model` objects:

.. code-block:: python

   from edsl import Model, ModelList, Survey

   models = ModelList(Model(m) for m in ['gpt-4o', 'gemini-1.5-flash'])

   survey = Survey.example()

   results = survey.by(models).run()


This will generate a result for each question in the survey with each model.
If agents and/or scenarios are also specified, the responses will be generated for each combination of agents, scenarios and models.
Each component is added with its own `by()` method, the order of which does not matter.
The following commands are equivalent:

.. code-block:: python

   # add code for creating survey, scenarios, agents, models here ...

   results = survey.by(scenarios).by(agents).by(models).run()

   # this is equivalent:
   results = survey.by(models).by(agents).by(scenarios).run()


Default model
-------------

If no model is specified, a survey is automatically run with the default model. 
Run `Model()` to check the current default model.
For example, the following code runs the example survey with the default model (and no agents or scenarios) without needing to import the `Model` class:

.. code-block:: python

   from edsl import Survey

   results = Survey.example().run()


We can verify the model that was used:

.. code-block:: python

   results.select("model.model") # selecting only the model name


Output:

.. list-table::
   :header-rows: 1

   * - model
   * - gpt-4o


Inspecting model parameters
---------------------------

We can also inspect parameters of the models that were used by calling the `models` method on the `Results` object.
For example, we can verify the default model when running a survey without specifying a model:

.. code-block:: python

   from edsl import Survey, Model, ModelList

   m = ModelList.from_names(["gpt-4o", "gemini-1.5-flash"])

   survey = Survey.example()

   results = survey.by(m).run()

   results.models


This will return the same information as the `ModelList` created above.

To learn more about all the components of a `Results` object, please see the :ref:`results` section.


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

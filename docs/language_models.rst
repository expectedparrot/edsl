.. _language_models:

Language Models
===============

Language models are used to generate responses to survey questions.
EDSL works with many models from a variety of popular inference service providers, including Anthropic, Azure, Bedrock, Deep Infra, DeepSeek, Google, Mistral, OpenAI, Perplexity and Together.
Current model pricing and performance information can be found at the Coop `model pricing and performance page <https://www.expectedparrot.com/getting-started/models>`_.

We also recommend checking providers' websites for the most up-to-date information on models and service providers' terms of use.
Links to providers' websites can be found at the models page.
If you need assistance checking whether a model is working or to report a missing model or price, please send a message to info@expectedparrot.com or post a message on `Discord <https://discord.com/invite/mxAYkjfy9m>`_.

This page provides examples of methods for specifying models for surveys using the `Model` and `ModelList` classes.



API keys 
--------

In order to use a model, you need to have an API key for the relevant service provider.
EDSL allows you to choose whether to provide your own keys from service providers or use an Expected Parrot API key to access all available models at once.
See the :ref:`api_keys` page for instructions on storing and prioritizing keys.


Available services 
------------------

The following code will return a table of inference service providers:

.. code-block:: python

  from edsl import Model

  Model.services()


Output:

.. list-table::
   :header-rows: 1

   * - Service Name
   * - anthropic
   * - azure
   * - bedrock
   * - deep_infra
   * - deepseek
   * - google
   * - groq
   * - mistral
   * - ollama
   * - openai
   * - perplexity
   * - together
   * - xai


.. Available models
.. ----------------

.. The following code will return a table of models for all service providers that have been used with EDSL (output omitted here for brevity).

.. This list should be used together with the `model pricing page <https://www.expectedparrot.com/getting-started/models>`_ to check current model performance with test survey questions.
.. We also recommend running your own test questions with any models that you want to use before running a large survey.

.. .. code-block:: python

..   from edsl import Model

..   Model.available()


.. To see a list of all models for a specific service, pass the service name as an argument:

.. .. code-block:: python

..    Model.available(service = "google")


.. Output (this list will vary based on the models that have been used when the code is run):

..   :header-rows: 1

..   * - Model Name
..     - Service Name
..   * - gemini-pro
..     - google
..   * - gemini-1.0-pro
..     - google
..   * - gemini-1.0-flash
..     - google
..   * - gemini-1.0-flash-8b
..     - google
..   * - gemini-1.5-pro
..     - google
..   * - gemini-2.0-flash
..     - google


.. Check working models 
.. --------------------

.. You can check current performance and pricing for models by running the following code:

.. .. code-block:: python

..   from edsl import Model

..   Model.check_working_models()


.. This will return the same information available at the `model pricing page <https://www.expectedparrot.com/getting-started/models>`_: *Service, Model, Works with text, Works with images, Price per 1M input tokens (USD), Price per 1M output tokens (USD)*.
.. It can also be used to check a particular service provider (output omitted here for brevity):

.. .. code-block:: python

..   from edsl import Model

..   Model.check_working_models(service = "google")


Specifying a model
------------------

To specify a model to use with a survey, create a `Model` object and pass it the name of the model.
You can optionally set other model parameters at the same time (temperature, etc.). 
You will sometimes need to specify the name of the service provider as well (for instance, if the model is hosted by multiple service providers).

For example, the following code creates a `Model` object for `gpt-4o` with default model parameters that we can inspect:

.. code-block:: python

  from edsl import Model

  m = Model("gpt-4o")


This is equivalent:

.. code-block:: python

  from edsl import Model

  m = Model(model = "gpt-4o", service_name = "openai")
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


We can see that the object consists of a model name and a dictionary of the default parameters of the model, together with the name of the inference service (some models are provided by multiple services).

Here we also specify the temperature when creating the `Model` object:


.. code-block:: python

  from edsl import Model

  m = Model("gpt-4o", service_name = "openai", temperature = 1.0)
  m


Output: 

.. list-table::
   :header-rows: 1

   * - key
     - value 
   * - model
     - gpt-4o
   * - parameters:temperature
     - 1.0
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



Creating a list of models
-------------------------

To create a list of models at once, pass a list of model names to a `ModelList` object.

For example, the following code creates a `Model` for each of `gpt-4o` and `gemini-pro`:

.. code-block:: python

  from edsl import Model, ModelList

  ml = ModelList([
    Model("gpt-4o", service_name = "openai"), 
    Model("gemini-1.5-flash", service_name = "google")
  ])


This code is equivalent to the following:

.. code-block:: python

  from edsl import Model, ModelList

  ml = ModelList(Model(model) for model in ["gpt-4o", "gemini-1.5-flash"])


We can also use a special method to pass a list of names instead:

.. code-block:: python

  from edsl import Model, ModelList

  model_names = ['gpt-4o', 'gemini-1.5-flash']

  ml = ModelList.from_names(model_names)

  ml


Output:

.. list-table::
   :header-rows: 1

   * - topK	
     - presence_penalty	
     - top_logprobs	
     - topP	
     - temperature	
     - stopSequences	
     - maxOutputTokens	
     - logprobs	
     - max_tokens	
     - frequency_penalty	
     - model	
     - top_p	
     - inference_service
   * - nan	
     - 0.000000	
     - 3.000000	
     - nan	
     - 0.500000	
     - nan	
     - nan	
     - False	
     - 1000.000000	
     - 0.000000	
     - gpt-4o	
     - 1.000000	
     - openai
   * - 1.000000	
     - nan	
     - nan	
     - 1.000000	
     - 0.500000	
     - []	
     - 2048.000000	
     - nan	
     - nan	
     - nan	
     - gemini-1.5-flash	
     - nan	
     - google


Running a survey with models
----------------------------

Similar to how we specify :ref:`agents` and :ref:`scenarios` to use with a survey, we specify the models to use by adding them to a survey with the `by()` method when the survey is run.
We can pass either a single `Model` object or a list of models to the `by()` method. 
If multiple models are to be used they are passed as a list or as a `ModelList` object.

For example, the following code specifies that a survey will be run with each of `gpt-4o` and `gemini-1.5-flash`:

.. code-block:: python

  from edsl import Model, QuestionFreeText, Survey

  m = [Model("gpt-4o", service_name = "openai"), Model("gemini-1.5-flash", service_name = "google")]

  q = QuestionFreeText(
    question_name = "example",
    question_text = "What is the capital of France?"
  )

  survey = Survey(questions = [q])

  results = survey.by(m).run()


This code uses `ModelList` instead of a list of `Model` objects:

.. code-block:: python

  from edsl import Model, ModelList, QuestionFreeText, Survey

  ml = ModelList(Model(model) for model in ["gpt-4o", "gemini-1.5-flash"])

  q = QuestionFreeText(
    question_name = "example",
    question_text = "What is the capital of France?"
  )

  survey = Survey(questions = [q])

  results = survey.by(ml).run()


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

For example, the following code runs the above survey with the default model (and no agents or scenarios) without needing to import the `Model` class:

.. code-block:: python

  results = survey.run() # using the survey from above

  # this is equivalent
  results = survey.by(Model()).run()


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

We can also inspect parameters of the models that were used by calling the `models` of the `Results` object.

For example, we can verify the default model when running a survey without specifying a model:

.. code-block:: python

  results.models # using the results from above


This will return the same information as running `results.select("model.model")` in the example above.

To learn more about all the components of a `Results` object, please see the :ref:`results` section.


Troubleshooting
---------------

Newly released models of service providers are automatically made available to use with your surveys whenever possible (not all service providers facilitate this).

If you do not see a model that you want to work with or are unable to instantiate it using the standard method, please send us a request to add it to *info@expectedparrot.com*.


.. Adding a model
.. --------------

.. You can add a model yourself by calling the `add_model()` method:


.. .. code-block:: python

..    from edsl import Model

..    Model.add_model(service_name = "google", model_name = "new_model")


.. This will add the model `new_model` to the `google` service.
.. You can then see the model in the list of available models, and search by service name:

.. .. code-block:: python

..    Model.available(service = "google")


.. Output:



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

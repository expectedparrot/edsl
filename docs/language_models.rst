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
For example, the following code creates a `Model` object for the GPT 4 model:

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
For example, the following code runs a job with the default model (and no agents or scenarios):

.. code-block:: python

   results = survey.run()



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
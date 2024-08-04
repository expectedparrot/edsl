.. _api_keys:

API Keys
========
API keys are required to access the services of large language models (LLMs) such as OpenAI's GPTs, Google's Gemini, Anthropic's Claude, Llama 2 and others.

To access LLMs using EDSL you can either use remote inference or local inference.


Remote inference 
----------------

This method allows you to run EDSL surveys on the Expected Parrot server instead of your local machine and avoid managing your own API keys for different LLM providers.

To use remote inference you must activate it at your :ref:`coop` account and store your Expected Parrot API key in a `.env` file in your working directory.
Your `.env` file should include the following line (replace `your_key_here` with your actual Expected Parrot API key from your Coop account):

.. code-block:: python

   EXPECTED_PARROT_API_KEY='your_key_here'


Please see the :ref:`remote_inference` section for instructions on how to activate remote inference and use it.


Local inference 
---------------

You can access LLMs with EDSL on your own machine by providing your own API keys for LLMs.

There are two ways of providing your own API keys to EDSL:


1. Using a .env file (*recommended*)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a `.env` file in your working directory and populate it with your API keys.
Replace `your_key_here` with your actual API key for each service that you plan to use:

.. code-block:: python

   ANTHROPIC_API_KEY='your_key_here'
   DEEP_INFRA_API_KEY='your_key_here'
   GOOGLE_API_KEY='your_key_here'
   OPENAI_API_KEY='your_key_here'


Using a `.env file` allows you to store your keys once and avoid repeatedly enter your API keys each time you start a session with EDSL.


2. Setting API keys in your Python code
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Alternatively, you can directly set your API keys in your Python script before importing any EDSL objects. 
This method stores the keys in your system's memory only for the duration of the session:

.. code-block:: python

   import os
   os.environ['ANTHROPIC_API_KEY'] = 'your_key_here'
   os.environ['DEEP_INFRA_API_KEY'] = 'your_key_here'
   os.environ['GOOGLE_API_KEY'] = 'your_key_here'
   os.environ['OPENAI_API_KEY'] = 'your_key_here'


Remember, if you restart your session, you will need to re-enter your API keys.
It is also important to remove your API keys from your code before sharing it with others.


Caution
~~~~~~~
Treat your API keys as sensitive information, akin to passwords. 
Never share them publicly or upload files containing your API keys to public repositories.


Troubleshooting
~~~~~~~~~~~~~~~
In addition to API keys, you must also have credits available on your account with a language model provider in order to run surveys with some models.

If you do not specify a model to use for a survey, EDSL will attempt to run it with the default model; currently, this is GPT 4 Preview.
In practice, this means that the following sets of commands are equivalent:

*Version 1*:

.. code-block:: python

   results = survey.run()


*Version 1*:

.. code-block:: python

   from edsl import Model 

   results = survey.by(Model('gpt-4-1106-preview')).run()


*Version 1*:

.. code-block:: python

   from edsl import Model 

   model = Model('gpt-4-1106-preview')

   results = survey.by(model).run()


If you have not provided an API key for the default model you will receive an error message about an exception.
You may also receive an error message if you do not have credits on your account with the model provider.
A common exception for this problem is an `AuthenticationError` about API keys: `Incorrect API key provided...`

To resolve this issue, you can either provide the correct API key for the default model (and ensure that you have credits from the provider) or specify a different model to use for the survey.

See more information on the available models in the  :ref:`language_models` section of the documentation.


Please also feel free to reach out to us to help you troubleshoot:

* Discord channel: https://discord.com/invite/mxAYkjfy9m
* Email: info@expectedparrot.com
.. _api_keys:

API Keys
========

API keys are required to access the services of large language models (LLMs) such as OpenAI's GPTs, Google's Gemini, Anthropic's Claude, Llama 2, Groq and others.

To run EDSL surveys with LLMs you can either provide your own API keys (for *local inference*) or use an Expected Parrot API key to access all available models at once at the Expected Parrot server (*remote inference*).
See more details on these methods below.


Special note for Colab users
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

If you are using EDSL in a Colab notebook, please see `special instructions <https://docs.expectedparrot.com/en/latest/colab_setup.html>`_ on optionally storing API keys as "secrets" in lieu of using an `.env` file as described below (:ref:`colab_setup`).


Storing API keys
----------------

EDSL provides two methods for storing API keys:

**1. Using a .env file (recommended)**

Create a file named `.env` in your EDSL working directory and populate it with your API keys using the template below.
Replace `your_key_here` with your actual API key for each service that you plan to use (you do not need to include keys for services that you do not plan to use):

.. code-block:: python

  # for remote inference
  EXPECTED_PARROT_API_KEY='your_key_here' 

  # for local inference
  ANTHROPIC_API_KEY='your_key_here'
  DEEP_INFRA_API_KEY='your_key_here'
  GOOGLE_API_KEY='your_key_here'
  GROQ_API_KEY='your_key_here'
  MISTRAL_API_KEY='your_key_here'
  OPENAI_API_KEY='your_key_here'
  REPLICATE_API_KEY='your_key_here'


AWS Bedrock requires multiple keys:

.. code-block:: python

  AWS_ACCESS_KEY_ID='your_key_here'
  AWS_SECRET_ACCESS_KEY='your_key_here'
  AZURE_ENDPOINT_URL_AND_KEY='your_key_here'


Using a `.env file` allows you to store your keys once and avoid repeatedly entering them each time that you start a session with EDSL.


**2. Setting API keys in your Python code**

Alternatively, you can directly set your API keys in your Python script before importing any EDSL objects using the template below.
This method stores the keys in your system's memory only for the duration of the session:

.. code-block:: python

  import os

  os.environ['EXPECTED_PARROT_API_KEY'] = 'your_key_here' 

  os.environ['ANTHROPIC_API_KEY'] = 'your_key_here'
  os.environ['DEEP_INFRA_API_KEY'] = 'your_key_here'
  os.environ['GOOGLE_API_KEY'] = 'your_key_here'
  os.environ['GROQ_API_KEY'] = 'your_key_here'
  os.environ['MISTRAL_API_KEY'] = 'your_key_here'
  os.environ['OPENAI_API_KEY'] = 'your_key_here'
  os.environ['REPLICATE_API_KEY'] = 'your_key_here'


Remember, if you restart your session, you will need to re-enter your API keys.
It is also important to remove your API keys from your code before sharing it with others.


Remote inference 
----------------

This method allows you to purchase :ref:`credits` to run EDSL surveys at the Expected Parrot server instead of your local machine, and avoid managing your own API keys for different service providers.

To use remote inference you must activate it at your `Coop <https://www.expectedparrot.com/home/api>`_ account and store your Expected Parrot API key in a file named `.env` in your EDSL working directory.
Your `.env` file should include the following line (replace `your_key_here` with your actual Expected Parrot API key from your Coop account):

.. code-block:: python

  EXPECTED_PARROT_API_KEY='your_key_here'


If you do not already have a file named `.env` in your working directory, you can create one and add the line above by running the following code:

.. code-block:: python

  with open(".env", "w") as f:
    f.write("EXPECTED_PARROT_API_KEY='your_key_here'")


If you attempt to run a survey without any API keys stored, you will receive a message with a link to log into Coop and automatically activate remote inference and store your Expected Parrot API key for you.

Please see the :ref:`remote_inference` section for more details on how to use remote inference with EDSL, and the :ref:`credits` section for information on purchasing credits and calculating costs.


Local inference 
---------------

You can access LLMs with EDSL on your own machine by providing your own API keys for LLMs.

To use local inference, ensure that your accounts with service providers have available funds and that you have access to the models that you want to use with EDSL.


Caution
-------

Treat your API keys as sensitive information, akin to passwords. 
Never share them publicly or upload files containing your API keys to public repositories.


Troubleshooting
---------------

In order to use local inference, you must also have credits available on your account with a service provider in order to run surveys with some models.
If you are using remote inference, simply ensure that you have credits on your Expected Parrot account to access all available models.

When you run a survey, EDSL checks whether you are using remote or local inference and then checks for the requisite API keys for the models that you have specified to use with the survey.
If you do not specify a model to use for a survey, EDSL will attempt to run it with the default model.
You can check the current default model by running the following command:

.. code-block:: python

  from edsl import Model
  Model()


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


To check all available models:

.. code-block:: python

  from edsl import Model
  Model.available()


To check all available models for a specific provider:

.. code-block:: python

  from edsl import Model
  Model.available(service="openai")


Learn more about available models in the :ref:`language_models` section of the documentation.

If you attempt to run a survey without storing any API keys, you will get a message with a link to log into Coop and automatically activate remote inference and store your Expected Parrot API key for you.  

If you provide an invalid API key you will receive an error message `AuthenticationError: Incorrect API key provided...`.
You may also receive an error message if you do not have credits on your account with a service provider.

Learn more about handling errors in the :ref:`exceptions` section of the documentation.

Please also feel free to reach out to us to help you troubleshoot:

* Discord channel: https://discord.com/invite/mxAYkjfy9m
* Email: info@expectedparrot.com

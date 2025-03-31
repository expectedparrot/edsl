.. _api_keys:

Managing Keys
=============

API keys are required to access large language models.
To use EDSL with models you can either provide your own keys from service providers (*Anthropic, Azure, Bedrock, Deep Infra, DeepSeek, Google, Groq, Mistral, OpenAI, Perplexity, Together, Xai*) or use an **Expected Parrot key** to access all available models at the Expected Parrot server. 
See the `model pricing page <http://www.expectedparrot.com/getting-started/coop-pricing>`_ for details on current available models and prices.

In addition to providing access to all available models, your Expected Parrot key also allows you to post and share content at `Coop <https://www.expectedparrot.com/content/explore>`_: a free platform for AI-based research that is fully integrated with EDSL. 
`Learn more <http://www.expectedparrot.com/getting-started/coop-how-it-works>`_ about using Coop to collaborate on research.

This page shows how to store and select keys to use when running surveys on your own computer (*local inference*) or at the Expected Parrot server (*remote inference*).
For instructions on using your Expected Parrot key only for accessing Coop, please see the `Coop section <https://docs.expectedparrot.com/en/latest/coop.html>`_ of the documentation.

**Special note for Colab users**:
If you are using EDSL in a Colab notebook, please see `special instructions <https://docs.expectedparrot.com/en/latest/colab_setup.html>`_ on storing API keys as "secrets" (:ref:`colab_setup`).

*Caution: Treat your API keys as sensitive information, like passwords. 
Never share your keys publicly or upload files containing them to public repositories.*


Methods
-------

There are three methods for storing and managing keys (details on each below):

  1. Manage keys from your Coop account (*recommended*)
  2. Store keys in a local file on your computer
  3. Set keys in your code (*not recommended*)


1. Manage keys from your account
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This method provides a secure way to store your keys and the most flexibility in choosing how to use them.
It requires a Coop account (`log in/sign up here <https://www.expectedparrot.com/login>`_) and works with :ref:`remote-inference`.

*If you are only running surveys locally, see method 2. below for instructions on storing keys on your computer.*

To use this method, go to your `Settings <http://www.expectedparrot.com/home/settings>`_ page and activate remote inference:

.. image:: static/home-settings.png
  :alt: Toggle on/off remote inference
  :align: center
  :width: 100%
  

.. raw:: html

  <br>


Then go to your `Keys <http://www.expectedparrot.com/home/keys>`_ page and choose whether to add any of your own keys.
Use the **Share** button to grant other users access to your keys and set limits on usage, without sharing the keys directly.
Use the **Edit** button to modify RPM and TPM rate limits for any of your keys, edit sharing permissions, or disable or delete your keys at any time.

You can review the current prioritization of your keys at the **Key priority** section of the page at any time.
When you run surveys remotely, your Expected Parrot key is used by default with any models that you have not provided keys for.

.. image:: static/home-keys.png
  :alt: View stored keys
  :align: center
  :width: 100%
  

.. raw:: html

  <br>



2. Store keys in a local file
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This method allows you to store keys in a private file on your computer and make them available for any surveys that you run, locally or remotely.
It also allows you to post local content to Coop.

To use this method:

1. Navigate to your EDSL working directory: `$ cd /path/to/edsl` (replace with your actual path)

2. Create a file named `.env`

3. Add your keys to the file in the following format (omit any keys that you do not have or do not want to use):

.. code-block:: python

  EXPECTED_PARROT_API_KEY = 'your_key_here' # This key is required for remote inference and interacting with Coop

  ANTHROPIC_API_KEY = 'your_key_here'
  DEEP_INFRA_API_KEY = 'your_key_here'
  DEEPSEEK_API_KEY = 'your_key_here'
  GOOGLE_API_KEY = 'your_key_here'
  GROQ_API_KEY = 'your_key_here'
  MISTRAL_API_KEY = 'your_key_here'
  OPENAI_API_KEY = 'your_key_here'
  PERPLEXITY_API_KEY = 'your_key_here'
  TOGETHER_API_KEY = 'your_key_here'
  XAI_API_KEY = 'your_key_here'
  
  AWS_ACCESS_KEY_ID = 'your_key_here'
  AWS_SECRET_ACCESS_KEY = 'your_key_here'
  
  AZURE_ENDPOINT_URL_AND_KEY = https://model_1_link:api_key_1,https://model_2_link:api_key_2


Your Expected Parrot key can be found at the `Settings <http://www.expectedparrot.com/home/settings>`_ page of your account, where you can reset it at any time. 
This key allows you to access all available models at once and use :ref:`remote-inference` to run surveys at the Expected Parrot server. 
It also allows you to post content to Coop, and to interact with other content that is public or shared with you.

If you are using Azure or Bedrock, see a notebook of examples for setting up your keys `here <https://docs.expectedparrot.com/en/latest/edsl_with_cloud_providers.html>`_.


3. Set keys in your code
^^^^^^^^^^^^^^^^^^^^^^^^

*Warning:* This method is not recommended for security reasons. 
If you include your keys in your code, they can be seen by anyone who has access to it. 
This is especially risky if you are sharing your code with others or if you are using a version control system like Git.

To use this method, store any keys that you want to use as strings in your code in the following format:

.. code-block:: python

  import os

  os.environ['EXPECTED_PARROT_API_KEY'] = 'your_key_here' 

  os.environ['ANTHROPIC_API_KEY'] = 'your_key_here'
  os.environ['DEEP_INFRA_API_KEY'] = 'your_key_here'
  os.environ['DEEPSEEK_API_KEY'] = 'your_key_here'
  os.environ['GOOGLE_API_KEY'] = 'your_key_here'
  os.environ['GROQ_API_KEY'] = 'your_key_here'
  os.environ['MISTRAL_API_KEY'] = 'your_key_here'
  os.environ['OPENAI_API_KEY'] = 'your_key_here'
  os.environ['REPLICATE_API_KEY'] = 'your_key_here'
  os.environ['TOGETHER_API_KEY'] = 'your_key_here'
  os.environ['XAI_API_KEY'] = 'your_key_here'

  os.environ['AWS_ACCESS_KEY_ID'] = 'your_key_here'
  os.environ['AWS_SECRET_ACCESS_KEY'] = 'your_key_here'
  
  os.environ['AZURE_ENDPOINT_URL_AND_KEY'] = https://model_1_link:api_key_1,https://model_2_link:api_key_2


Note that your keys will not persist across sessions and you will need to provide your keys each time you start a new session.


Credits 
-------

When you use your Expected Parrot key to access models your account is charged for the costs of API calls to models.
(When you use your own keys, service providers will bill you directly.)
Please see the `model pricing page <http://www.expectedparrot.com/getting-started/coop-pricing>`_ for information on available models and prices and the :ref:`credits` section for information on purchasing credits and calculating costs.


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

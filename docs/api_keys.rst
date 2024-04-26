.. _api_keys:

API Keys
========
API keys are required to access the services of large language models (LLMs) such as OpenAI's GPTs, Google's Gemini, Anthropic's Claude, Llama 2 and others.

There are two methods for securely providing your API keys to EDSL:


1. Using a .env file (*recommended*)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a `.env` file in your working directory and populate it with your API keys.
Replace `your_key_here` with your actual API keys for each service you plan to use:

.. code-block:: python

   ANTHROPIC_API_KEY=your_key_here
   DEEP_INFRA_API_KEY=your_key_here
   GOOGLE_API_KEY=your_key_here
   OPENAI_API_KEY=your_key_here


By using a .env file, you avoid the need to repeatedly enter your API keys each time you start a session with EDSL.


2. Setting API keys in your Python code
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Alternatively, you can directly set your API keys in your Python script before importing any EDSL objects. 
This method stores the keys in your system's memory only for the duration of the session:

.. code-block:: python

   import os
   os.environ['ANTHROPIC_API_KEY'] = 'your_key_here'
   os.environ['DEEP_INFRA_API_KEY'] = 'your_key_here'
   os.environ['GOOGLE_API_KEY'] = 'your_key_here'
   os.environ['OPENAI_API_KEY'] = 'your_key_here'


Remember, if you restart your session, you will need to re-enter your API keys.


Caution
~~~~~~~
Treat your API keys as sensitive information, akin to passwords. 
Never share them publicly or upload files containing your API keys to public repositories.


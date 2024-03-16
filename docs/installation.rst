Installing EDSL
===============

Requirements
------------

.. raw:: html
  
    Python 3.9 - 3.11 (<a href="https://www.python.org/downloads/" target="_blank">https://www.python.org/downloads/</a>)

`Expected Parrot account <#expected-parrot-account>`__ or your own
API keys for OpenAI, Google and/or DeepInfra (to access language
models such as GPT 4).

Installation
------------

.. raw:: html
  
  The EDSL library is available on PyPI: <a href="https://pypi.org/project/edsl/" target="_blank">https://pypi.org/project/edsl/</a>.

Quickstart
~~~~~~~~~~

Run the following commands to install or update your version of EDSL on
your computer.

Install EDSL:

.. code:: 

    pip install edsl

Check your version is up to date (compare the output message of this
command to the version listed at PyPI):

.. code:: 

    pip show edsl

Update your version:

.. code:: 

    pip install --upgrade edsl

Advanced
~~~~~~~~

The Quickstart installation steps above will install EDSL globally on
your system. Sometimes, you may face problems with conflicts between
EDSL and other packages. To avoid any problems, we recommend using a
virtual environment when working with EDSL.

Open your terminal and run:

.. code:: 

    python3 -m venv myenv

This will create a folder called myenv. Next, activate your virtual
environment:

.. code:: 

    source myenv/bin/activate

You can now install EDSL through pip within your virtual environment:

.. code:: 

    pip install edsl

You will have access to EDSL while your virtual environment is
activated.

You can deactivate the virtual environment at any time by running:

.. code:: 

    deactivate

To delete the virtual environment, simply delete the myenv folder.

Notes
~~~~~

-  Collaboration environments such as Deepnote, Google Collab and Github
   Gists may require you to install the EDSL library whenever you use
   it.
-  In your personal system you should only need to install EDSL once,
   and then check for update

API keys
--------

The first time that you import tools from the EDSL library (i.e.,
running any code blocks that begin with ``from edsl import ...``) you
will be prompted to provide API keys for language models.

There are 3 separate prompts for OpenAI, Google and DeepInfra that like
this:

::

   ==================================================
   Please provide your OpenAI API key (https://platform.openai.com/api-keys).
   If you would like to skip this step, press enter.
   If you would like to provide your key, do one of the following:
   1. Set it as a regular environment variable
   2. Create a .env file and add `OPENAI_API_KEY=...` to it
   3. Enter the value below and press enter: 

At each prompt, you can either enter an API key or skip it by pressing
enter/return.

API keys are required in order to generate survey results with LLMs like
GPT-3.5 and GPT-4. 

.. raw:: html
  
    <a href="https://platform.openai.com/api-keys" target="_blank">OpenAI API</a>
    <a href="https://cloud.google.com/docs/authentication/getting-started" target="_blank">Google Cloud</a>

Expected Parrot account
-----------------------

Create an account to get the Expected Parrot API key which provides
access to all available language models and hosting for all of your
results. Each new account comes with free tokens for getting started:

.. raw:: html
  
    <a href="https://www.expectedparrot.com/signup" target="_blank">https://www.expectedparrot.com/signup</a>

--------------

.. raw:: html

   <p style="font-size: 14px;">

Copyright © 2024 Expected Parrot, Inc. All rights reserved.
www.expectedparrot.com

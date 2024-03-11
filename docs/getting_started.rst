E[🦜]: Getting started with edsl
================================

Requirements
------------

- Python 3.9 - 3.11

- For now API key for OpenAI, Google and/or DeepInfra — Stay tuned, the edsl API is coming soon!

Installation
------------

Check for the latest version of edsl on PyPI: 

.. _pypi: https://pypi.org/project/edsl/

.. _GitHub: https://github.com/expectedparrot/edsl/

.. _Discord: https://discord.com/invite/mxAYkjfy9m

See examples, demo notebooks, and FAQ below.

.. code-block:: shell

    pip install edsl

Updating your version
---------------------

.. code-block:: shell

    pip install --upgrade edsl

Checking your version
---------------------

.. code-block:: shell

    pip show edsl

API keys
--------

You will be prompted to provide API keys when you first access the package. You can skip this step by pressing return/enter. 
API keys are not required to construct surveys using edsl; however, you will need an API key in order to simulate responses using LLMs.

Note: The edsl API is coming soon! It will allow you to access all of the available LLMs with a single key managed by Expected Parrot.

A quick example
---------------

Steps to create a question, administer it to an LLM, and inspect the result:

.. code-block:: python

    from edsl import QuestionMultipleChoice
    from edsl import Model 
    m = Model("gpt-3.5-turbo")
    q = QuestionMultipleChoice(
        question_text = "What is the capital of France?", 
        question_options = ["Paris", "London", "Berlin", "Madrid"],
        question_name = "capital_of_france"
    )
    q.run() 

Which will return:

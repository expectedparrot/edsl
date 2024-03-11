E[🦜]: Getting started with edsl
================================

Requirements
------------

- Python 3.9 - 3.11

- For now, API keys for OpenAI, Google and/or DeepInfra — Stay tuned, the edsl API is coming soon!

Installation
------------

Check for the latest version of edsl on PyPI: https://pypi.org/project/edsl/

View the source code on GitHub: https://github.com/expectedparrot/edsl/

Installing the latest version
-----------------------------

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

Create a question, administer it to an AI agent, and inspect the results:

.. code-block:: python

    from edsl import QuestionMultipleChoice
    from edsl import Agent, Model 
    a = Agent(traits={"persona": "You are an expert hydrologist."})
    m = Model("gpt-3.5-turbo")
    q = QuestionMultipleChoice(
        question_name = "water",
        question_text = "What is H2O?", 
        question_options = ["Gold", "Water", "Air", "Fire"]
    )
    results = q.by(a).by(m).run() 

Tutorials, demo notebooks & FAQ
--------------

Access a broad range of tutorials on getting started, examples, demos and FAQ at our main page: https://www.expectedparrot.com/getting-started

Reach out to us if you need any help getting started! We're happy to build a notebook for you.

Community 
---------

Join our Discord: https://discord.com/invite/mxAYkjfy9m

Follow us on X: https://twitter.com/expectedparrot

Follow us on LinkedIn: https://www.linkedin.com/company/expectedparrot 

Send us an email: info@expectedparrot.com 
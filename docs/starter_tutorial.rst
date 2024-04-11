.. _starter_tutorial:

Starter Tutorial
================
This page provides a guide for getting started running your first AI-powered research! 
Please let us know if you have any questions or need help by contacting us at info@expectedparrot.com or posting a message in our Discord channel: https://discord.com/invite/mxAYkjfy9m.

.. raw:: html

    You can also view the contents of this tutorial in an <a href="https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Tutorial%20-%20Starter%20Tutorial-e080f5883d764931960d3920782baf34" target="_blank">interactive notebook</a>.


Part 1: Using API Keys for LLMs
-------------------------------
Large language models (LLMs) are at the heart of AI-powered research. 
EDSL allows you to easily conduct research with popular LLMs, including OpenAI's GPTs, Google's Gemini, Anthropic's Claude, Llama 2 and others. 
In order to do so, you must provide EDSL with your API keys that you obtain from LLM providers. 
*Note: EDSL will never store your personal API keys.*

There are 2 ways to provide your API keys to EDSL:

1. Use a .env file (*recommended*)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Create a file named `.env` in your working directory and populate it as follows, replacing `your_key_here` with your actual API keys:

.. code-block:: python

   ANTHROPIC_API_KEY=your_key_here
   DBRX_API_KEY=your_key_here
   DEEP_INFRA_API_KEY=your_key_here
   GOOGLE_API_KEY=your_key_here
   OPENAI_API_KEY=your_key_here

EDSL will read your API keys from this file.  
This method allows you to avoid having to provide your keys each time that you start a session with EDSL and is the recommended way to provide your API keys for this reason.

If you are not planning to use one or more of these providers you can comment out the relevant lines.
This will ensure that you get an error message if you accidentally try to use an LLM without a valid API key.

For example, if you only plan to use models provided by Anthropic, you can set your `.env` file as follows:

.. code-block:: python

   ANTHROPIC_API_KEY=your_key_here
   # DBRX_API_KEY=your_key_here
   # DEEP_INFRA_API_KEY=your_key_here
   # GOOGLE_API_KEY=your_key_here
   # OPENAI_API_KEY=your_key_here
   
2. Set your API keys in your Python code
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Instead of using an `.env` file, you can set your API keys in your Python code before you import any EDSL object as follows:

.. code-block:: python

   import os
   os.environ['ANTHROPIC_API_KEY'] = 'your_key_here'
   os.environ['DEEP_INFRA_API_KEY'] = 'your_key_here'
   os.environ['GOOGLE_API_KEY'] = 'your_key_here'
   os.environ['OPENAI_API_KEY'] = 'your_key_here'

Note that this will store your API keys in your system's memory only for the duration of your session. 
If you restart your session, you will need to set your API keys again.

If you are not planning to use one or more of these providers you can delete the line.
This will ensure that you get an error message if you accidentally try to use an LLM without a valid API key.

Caution
~~~~~~~
You should always treat your API keys like you treat your passwords: never share them or upload files with your API keys to any public repository.

Part 2: Conducting AI-powered research
--------------------------------------
With your API keys in place, you're now ready for AI-powered research!
In this part we show how to create and run a simple survey in just a few lines of code, and then create a proper survey with only slightly more work.

Quickstart Example
~~~~~~~~~~~~~~~~~~
Here we create a multiple choice question, prompt an AI agent answer it, and inspect the results:

.. code-block:: python 

    # Import a desired question type
    from edsl.questions import QuestionMultipleChoice
    
    # Construct a simple question
    q = QuestionMultipleChoice(
        question_name = "example_question",
        question_text = "How do you feel today?",
        question_options = ["Bad", "OK", "Good"]
    )
    
    # Prompt the default model to answer it (GPT-4)
    results = q.run()
    
    # Inspect the results
    results.select("example_question").print()

.. code-block:: text

    ┏━━━━━━━━━━━━━━━━━━━┓
    ┃ answer            ┃
    ┃ .example_question ┃
    ┡━━━━━━━━━━━━━━━━━━━┩
    │ Good              │
    └───────────────────┘


A Proper Survey
~~~~~~~~~~~~~~~
Here we create a more complex survey where we ask AI agents how much they enjoy different activities. 
We also create agents with different personas, and use different LLMs to generate the results:

.. code-block:: python

    # Import other desired question types - see examples of all types in the :ref:`questions` section.
    from edsl.questions import QuestionLinearScale, QuestionFreeText
    from edsl import Scenario, Survey, Agent, Model
    
    # Construct questions - note that we use a parameter `activity` in order to create multiple scenarios of the question texts
    q1 = QuestionLinearScale(
        question_name = "q1",
        question_text = "On a scale from 0 to 5, how much do you enjoy {{ activity }}?",
        question_options = [0,1,2,3,4,5]
    )
    
    q2 = QuestionFreeText(
        question_name = "q2",
        question_text = "Describe your habits with respect to {{ activity }}."
    )
    
    # Add values for the scenarios
    activities = ["exercising", "reading", "cooking"]
    scenarios = [Scenario({"activity": a}) for a in activities]
    
    # Combine the questions in a survey
    survey = Survey(questions = [q1, q2])
    
    # Create personas for agents that will respond to the survey
    personas = ["You are an athlete", "You are a student", "You are a chef"]
    agents = [Agent(traits = {"persona": p}) for p in personas]
    
    # Select language models
    models = [Model("gpt-3.5-turbo"), Model("gpt-4-1106-preview")]
    
    # Administer the survey 
    results = survey.by(scenarios).by(agents).by(models).run()
    
    # Select components of the results to view
    results.select("model.model", "scenario.activity", "agent.persona", "answer.*").print()

.. raw:: html

    View the results in an interactive notebook <a href="https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Tutorial%20-%20Starter%20Tutorial-e080f5883d764931960d3920782baf34" target="_blank">here</a>.


Exploring your results
~~~~~~~~~~~~~~~~~~~~~~
EDSL comes with built-in methods for analyzing and visualizing your results. 
For example, you can access results as a Pandas dataframe:

.. code-block:: python

    # Turn the Results object to a pandas dataframe
    results.to_pandas()

.. code-block:: python

    # The Results object has various attributes you can use
    results.columns

.. code-block:: python

    ['agent.agent_name',
     'agent.persona',
     'answer.q1',
     'answer.q1_comment',
     'answer.q2',
     'iteration.iteration', 
     'model.frequency_penalty', 
     'model.logprobs', 
     'model.max_new_tokens', 
     'model.max_tokens', 
     'model.model', 
     'model.presence_penalty', 
     'model.stopSequences', 
     'model.temperature', 
     'model.top_k', 
     'model.top_logprobs', 
     'model.top_p', 
     'model.use_cache', 
     'prompt.q1_system_prompt',
     'prompt.q1_user_prompt',
     'prompt.q2_system_prompt',
     'prompt.q2_user_prompt',
     'scenario.activity']


.. code-block:: python

    # The Results object also supports SQL-like queries
    results.sql("select * from self", shape="wide")

.. raw:: html

    View the output and examples of other methods in interactive notebooks <a href="https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Tutorial%20-%20Starter%20Tutorial-e080f5883d764931960d3920782baf34" target="_blank">here</a>.<br><br>
    Learn more about use cases and ways to conduct AI-powered research in the <a href="http://www.expectedparrot.com/getting-started#edsl-showcase" target="_blank">EDSL Showcase</a>.

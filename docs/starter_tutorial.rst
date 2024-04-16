.. _starter_tutorial:

Starter Tutorial
================
This tutorial will guide you through the initial steps required to run your first project using EDSL. 
If you encounter any issues or have questions, feel free to reach out via email at info@expectedparrot.com or join the discussion in our Discord channel: https://discord.com/invite/mxAYkjfy9m.


.. raw:: html

    You can also view the contents of this tutorial in an <a href="https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Tutorial%20-%20Starter%20Tutorial-e080f5883d764931960d3920782baf34" target="_blank">interactive notebook</a>.



Part 1: Using API Keys for LLMs
-------------------------------
Large language models (LLMs) are at the heart of AI-powered research. 
EDSL allows you to easily conduct research with popular LLMs, including OpenAI's GPTs, Google's Gemini, Anthropic's Claude, Llama 2 and others. 
To interact with these models with EDSL, you'll need to authenticate using API keys provided by the LLM services.

*Securing Your API Keys*

There are two recommended methods to securely provide your API keys to EDSL:

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
Comment out the API keys for any services you do not plan to use to avoid runtime errors:

.. code-block:: python

   ANTHROPIC_API_KEY=your_key_here
   # DEEP_INFRA_API_KEY=your_key_here
   # GOOGLE_API_KEY=your_key_here
   # OPENAI_API_KEY=your_key_here
   

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


Part 2: Conducting AI-powered research
--------------------------------------
With your API keys in place, we can move on to conducting AI-powered research!
In the steps below we show how to create and run a simple survey, and then explore a more detailed survey setup with AI agents and models.

Quickstart Example
~~~~~~~~~~~~~~~~~~
Here we create a basic multiple choice question, administer it to a language model, and examine the response:

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


Output:

.. code-block:: text

    ┏━━━━━━━━━━━━━━━━━━━┓
    ┃ answer            ┃
    ┃ .example_question ┃
    ┡━━━━━━━━━━━━━━━━━━━┩
    │ Good              │
    └───────────────────┘


A Proper Survey
~~~~~~~~~~~~~~~
Here we create a survey of questions and personas for AI agents that we prompt to answer the questions.
Note that we parameterize the questions in order to create different versions of the question texts.
We also use multiple LLMs to compare results for them:

.. code-block:: python

    # Select desired question types and survey components
    from edsl.questions import QuestionLinearScale, QuestionFreeText
    from edsl import Scenario, Survey, Agent, Model
    
    # Construct questions that take parameters
    q1 = QuestionLinearScale(
        question_name = "q1",
        question_text = "On a scale from 0 to 5, how much do you enjoy {{ activity }}?",
        question_options = [0,1,2,3,4,5]
    )
    
    q2 = QuestionFreeText(
        question_name = "q2",
        question_text = "Describe your habits with respect to {{ activity }}."
    )
    
    # Add values for the question scenarios
    activities = ["exercising", "reading", "cooking"]
    scenarios = [Scenario({"activity": a}) for a in activities]
    
    # Combine the questions in a survey
    survey = Survey(questions = [q1, q2])
    
    # Create personas for AI agents to use with the survey
    personas = ["You are an athlete", "You are a student", "You are a chef"]
    agents = [Agent(traits = {"persona": p}) for p in personas]
    
    # Select language models
    # To see all available models: Model.available()
    models = [Model("gpt-3.5-turbo"), Model("gpt-4-1106-preview")]
    
    # Run the survey with the scenarios, agents and models
    results = survey.by(scenarios).by(agents).by(models).run()
    
    # Select components of the results to review
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

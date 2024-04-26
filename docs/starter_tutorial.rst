.. _starter_tutorial:

Starter Tutorial
================
This tutorial will guide you through the steps required to run your first project using EDSL. 


Prerequisites
-------------
<mark>Before you begin, ensure that you have already completed the :ref:`installation` steps and stored your :ref:`api_keys` for the language models that you plan to use.</mark>

If you encounter any issues or have questions, feel free to reach out via email at info@expectedparrot.com or join the discussion in our `Discord channel <https://discord.com/invite/mxAYkjfy9m>`_.
You can also view the contents of this tutorial in an `interactive notebook <https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Tutorial%20-%20Starter%20Tutorial-e080f5883d764931960d3920782baf34>`_.


Conducting an AI-powered survey
-------------------------------
In the steps below we show how to create and run a simple survey, and then explore a more complex survey design with AI agents and various models.

1. **Create a simple survey**:
    - Import the desired question types from the `edsl.questions` module.
    - Construct a question using the desired question type.
    - Prompt the default model to answer the question.
    - Inspect the results.

2. **Create a proper survey**:
    - Select the desired question types and survey components.
    - Construct questions that take parameters.
    - Add values for the question scenarios.
    - Combine the questions in a survey.
    - Create personas for AI agents to use with the survey.
    - Select language models.
    - Run the survey with the scenarios, agents, and models.
    - Select components of the results to review.

3. **Explore your results**:
    - Analyze and visualize your results using built-in methods.
    - Convert the `Results` object to a Pandas dataframe.
    - Display a list of all the components of your results.
    - Execute an SQL-like query on the results.



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

You can view the results in an `interactive notebook <https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Tutorial%20-%20Starter%20Tutorial-e080f5883d764931960d3920782baf34>`_.


Exploring Your Results
~~~~~~~~~~~~~~~~~~~~~~
EDSL comes with built-in methods for analyzing and visualizing your results. 
For example, you can access results as a Pandas dataframe:

.. code-block:: python

    # Convert the Results object to a pandas dataframe
    results.to_pandas()


The `columns` method will display a list of all the components of your results, which you can then `select` and `print` to show them:

.. code-block:: python

    results.columns


Output for the results generated above:

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


The `Results` object also supports SQL-like queries:

.. code-block:: python

    # Execute an SQL-like query on the results
    results.sql("select * from self", shape="wide")

You can view the output and examples of other methods in `interactive notebooks <https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Tutorial%20-%20Starter%20Tutorial-e080f5883d764931960d3920782baf34>`_.




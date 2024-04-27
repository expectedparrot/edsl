.. _starter_tutorial:

Starter Tutorial
================
This tutorial will guide you through the steps required to run your first project using EDSL. 


Prerequisites
-------------
Before you begin, ensure that you have already completed the :ref:`installation` steps and stored your :ref:`api_keys` for the language models that you plan to use.

If you encounter any issues or have questions, please email us at info@expectedparrot.com or send post a question at our `Discord channel <https://discord.com/invite/mxAYkjfy9m>`_.
You can also view the contents of this tutorial in an `interactive notebook <https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Tutorial%20-%20Starter%20Tutorial-e080f5883d764931960d3920782baf34>`_.


Conducting an AI-powered survey
-------------------------------
In the steps below we show how to create and run a simple survey in EDSL, and then explore a more complex survey design with AI agents and various models.
The steps are as follows:

1. **Run a simple survey**:
    - Import a question type.
    - Construct a question in the question type template.
    - Prompt the default language model to answer the question.
    - Inspect the results.

2. **Design a survey with agents and models**:
    - Import question types and survey components.
    - Construct questions in the relevant templates.
    - Use parameters to create different versions of the questions.
    - Combine the questions in a survey.
    - Create personas for AI agents that will answer the questions.
    - Select language models.
    - Run the survey with the agents and models.
    - Explore built-in methods for analyzing results.


A Simple Survey
~~~~~~~~~~~~~~~
Here we create a basic multiple choice question, run it with the default language model and examine the response:

.. code-block:: python 

    # Import a question type
    from edsl.questions import QuestionMultipleChoice
    
    # Construct a question in the question type template
    q = QuestionMultipleChoice(
        question_name = "example_question",
        question_text = "How do you feel today?",
        question_options = ["Bad", "OK", "Good"]
    )
    
    # Run it with the default language model
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


Note: The default language model is currently GPT 4; you will need an API key for OpenAI to use this model and run this example.
In the example below we will show how to use different models to generate responses.


A Survey with Agents and Models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
In this next example we create a survey of multiple questions and personas for AI agents that will answer the questions.
We also show how to parameterize questions in order to create different versions of them that can be administered at once.
This is useful for comparing responses across different scenarios, and conducting data labeling tasks.
We also use multiple language models to compare results for them.

To see examples of all question types, you can run `Question.available()`.
To see all available models, you can run `Model.available()`.

.. code-block:: python

    # Select question types and survey components
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
    personas = [
        "You are an athlete", 
        "You are a student", 
        "You are a chef"
        ]

    agents = [Agent(traits = {"persona": p}) for p in personas]
    
    # Select language models
    models = [
        Model("gpt-3.5-turbo"), 
        Model("gpt-4-1106-preview")
        ]
    
    # Run the survey with the scenarios, agents and models
    results = survey.by(scenarios).by(agents).by(models).run()
    
    # Select components of the results to view
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




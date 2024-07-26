.. _starter_tutorial:

Starter Tutorial
================

This tutorial demonstrates basic steps for conducting an AI-powered survey using EDSL. 

*View this notebook at the Coop: https://www.expectedparrot.com/content/a1435acd-9a2c-45fb-adfd-226a7a6c0c97*


Prerequisites
-------------

Before running the code below, ensure that you have already completed technical setup:

- Download the EDSL package. See :ref:`installation` instructions.

- Create a :ref:`coop` account and activate :ref:`remote_inference` or store your own :ref:`api_keys` for language models that you plan to use locally.

If you encounter any issues or have questions, please email us at info@expectedparrot.com or post a question at our `Discord channel <https://discord.com/invite/mxAYkjfy9m>`_.


Conducting an AI-powered survey
-------------------------------

In the steps below we show how to create and run a simple question in EDSL. 
Then we show how to design a more complex survey with AI agents and different language models.


Run a simple question
~~~~~~~~~~~~~~~~~~~~~

In this first example we create a simple multiple choice question, administer it to a language model and inspect the response:

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


*Note:* The default language model is currently GPT 4; you will need an API key for OpenAI to use this model and run this example locally.
See instructions on storing your :ref:`api_keys`. 
Alternatively, you can activate :ref:`remote_inference` at your :ref:`coop` account to run the example on the Expected Parrot server.


Conduct a survey with agents and models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In this next example we create a survey of multiple questions, design personas for AI agents to answer the questions and select the language models that we want to generate the responses.
We also show how to parameterize questions with context or data to administer different versions of the questions efficiently.
This can be useful for comparing responses for different data, agents and models, and performing data labeling tasks.

We also show how to filter, sort, select and print components of the dataset of results.

To see examples of all EDSL question types, run:

.. code-block:: python

    from edsl import Question

    Question.available()


Newly released language models are automatically added to EDSL when they become available. 
To see a current list of available models, run:

.. code-block:: python

    from edsl import Model

    Model.available()
    

.. code-block:: python

    # Import question types and survey components
    from edsl import (
        QuestionLinearScale, QuestionFreeText, Survey,
        ScenarioList, Scenario, 
        AgentList, Agent, 
        ModelList, Model
    )

    # Construct questions
    q1 = QuestionLinearScale(
        question_name = "enjoy",
        question_text = "On a scale from 1 to 5, how much do you enjoy {{ activity }}?",
        question_options = [1,2,3,4,5],
        option_labels = {1:"Not at all", 5:"Very much"}
    )

    q2 = QuestionFreeText(
        question_name = "recent",
        question_text = "Describe the most recent time you were {{ activity }}."
    )

    # Combine questions in a survey
    survey = Survey(questions = [q1, q2])

    # Add data to questions using scenarios
    activities = ["exercising", "reading", "cooking"]

    scenarios = ScenarioList(
        Scenario({"activity": a}) for a in activities
    )

    # Create personas for AI agents to answer the questions
    personas = ["athlete", "student", "chef"]

    agents = AgentList(
        Agent(traits = {"persona": p}) for p in personas
    )

    # Select language models to generate responses
    models = ModelList(
        Model(m) for m in ["gpt-4o", "claude-3-5-sonnet-20240620"]
    )

    # Run the survey with the scenarios, agents and models
    results = survey.by(scenarios).by(agents).by(models).run()

    # Filter, sort, select and print components of the results to inspect
    (results
    .filter("activity == 'reading' and persona == 'chef'")
    .sort_by("model")
    .select("model", "activity", "persona", "answer.*")
    .print(format="rich",
            pretty_labels = ({"model.model":"Model",
                            "scenario.activity":"Activity",
                            "agent.persona":"Agent persona",
                            "answer.enjoy":"Enjoy",
                            "answer.recent":"Recent"})
        )
    )


Output:

.. code-block:: text

    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ Model                      ┃ Activity ┃ Agent persona ┃ Enjoy ┃ Recent                                          ┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ claude-3-5-sonnet-20240620 │ reading  │ chef          │ 4     │ As a chef, I recently found myself engrossed in │
    │                            │          │               │       │ a new cookbook featuring innovative             │
    │                            │          │               │       │ Mediterranean cuisine. I was curled up in my    │
    │                            │          │               │       │ favorite armchair, poring over vibrant photos   │
    │                            │          │               │       │ of colorful dishes and studying intricate       │
    │                            │          │               │       │ flavor combinations. The pages were filled with │
    │                            │          │               │       │ enticing recipes that sparked my culinary       │
    │                            │          │               │       │ imagination. I took notes on interesting        │
    │                            │          │               │       │ techniques and ingredient pairings, eager to    │
    │                            │          │               │       │ incorporate these fresh ideas into my own       │
    │                            │          │               │       │ cooking. Reading cookbooks is not just a        │
    │                            │          │               │       │ pastime for me; it's an essential part of my    │
    │                            │          │               │       │ professional development and a source of        │
    │                            │          │               │       │ endless inspiration in the kitchen.             │
    ├────────────────────────────┼──────────┼───────────────┼───────┼─────────────────────────────────────────────────┤
    │ gpt-4o                     │ reading  │ chef          │ 4     │ The most recent time I was reading, I was       │
    │                            │          │               │       │ flipping through a cookbook that focused on     │
    │                            │          │               │       │ Mediterranean cuisine. I was particularly       │
    │                            │          │               │       │ interested in a recipe for a traditional Greek  │
    │                            │          │               │       │ moussaka. The book had beautiful photographs    │
    │                            │          │               │       │ and detailed instructions, which really helped  │
    │                            │          │               │       │ me visualize the steps. I made some notes on    │
    │                            │          │               │       │ how I could add my own twist to the dish,       │
    │                            │          │               │       │ perhaps by incorporating some locally sourced   │
    │                            │          │               │       │ ingredients.                                    │
    └────────────────────────────┴──────────┴───────────────┴───────┴─────────────────────────────────────────────────┘


Exploring your results
~~~~~~~~~~~~~~~~~~~~~~
EDSL comes with built-in methods for analyzing and visualizing your results. 
For example, you can access results as a Pandas dataframe:

.. code-block:: python

    # Convert the Results object to a pandas dataframe
    results.to_pandas()


The `columns` method will display a list of all the components of your results, which you can then `select` and `print` to show them:

.. code-block:: python

    results.columns


Output:

.. code-block:: python

    ['agent.agent_instruction',
    'agent.agent_name',
    'agent.persona',
    'answer.enjoy',
    'answer.recent',
    'comment.enjoy_comment',
    'iteration.iteration',
    'model.frequency_penalty',
    'model.logprobs',
    'model.max_tokens',
    'model.model',
    'model.presence_penalty',
    'model.temperature',
    'model.top_logprobs',
    'model.top_p',
    'prompt.enjoy_system_prompt',
    'prompt.enjoy_user_prompt',
    'prompt.recent_system_prompt',
    'prompt.recent_user_prompt',
    'question_options.enjoy_question_options',
    'question_options.recent_question_options',
    'question_text.enjoy_question_text',
    'question_text.recent_question_text',
    'question_type.enjoy_question_type',
    'question_type.recent_question_type',
    'raw_model_response.enjoy_raw_model_response',
    'raw_model_response.recent_raw_model_response',
    'scenario.activity']


The `Results` object also supports SQL-like queries:

.. code-block:: python

    # Execute an SQL-like query on the results
    results.sql("select * from self", shape="wide")


Learn more about working with results in the :ref:`results` section.



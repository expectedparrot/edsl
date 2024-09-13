.. _starter_tutorial:

Starter Tutorial
================

This tutorial demonstrates basic steps for conducting an AI-powered survey using EDSL and storing it at the Coop. 
You can also `view this notebook at the Coop <https://www.expectedparrot.com/content/ef05e6dd-c176-4812-8143-46141d7f1833>`_.


Technical setup
---------------

Before running the code below, ensure that you have already completed technical setup:

1. Download the EDSL library. See :ref:`installation` instructions. 
2. Choose how you want to use EDSL:

    * Run surveys remotely on the Expected Parrot server by activating :ref:`remote_inference` at your :ref:`coop` account
    * Run surveys locally by storing your own :ref:`api_keys` for language models that you want to use with EDSL

If you encounter any issues or have questions, please email us at info@expectedparrot.com or post a question at our `Discord channel <https://discord.com/invite/mxAYkjfy9m>`_.


Conducting an AI-powered survey
-------------------------------

In the steps below we show how to create and run a simple question in EDSL. 
Then we show how to design a more complex survey with AI agents and different language models.


Running a simple question
~~~~~~~~~~~~~~~~~~~~~~~~~

Here we create a multiple choice question, administer it to the default language model (GPT 4 preview) and inspect the response:

.. code-block:: python 

    # Import a question type
    from edsl import QuestionMultipleChoice
    
    # Construct a question in the question type template
    q = QuestionMultipleChoice(
        question_name = "my_example",
        question_text = "How do you feel today?",
        question_options = ["Bad", "OK", "Good"]
    )
    
    # Run it with the default language model
    results = q.run()
    
    # Inspect the results
    results.select("my_example").print()


Output:

.. code-block:: text

    ┏━━━━━━━━━━━━━━━━━━━┓
    ┃ answer            ┃
    ┃ .my_question      ┃
    ┡━━━━━━━━━━━━━━━━━━━┩
    │ Good              │
    └───────────────────┘


*Note:* The default language model is currently GPT 4 preview; you will need an API key for OpenAI to run this example locally.
See instructions on storing your own :ref:`api_keys`. 
Alternatively, you can activate :ref:`remote_inference` at your :ref:`coop` account to run the example on the Expected Parrot server.


Conduct a survey with agents and models
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

In this next example we create a survey of multiple questions, design personas for AI agents to answer the questions and select the language models that we want to generate the responses.
We also show how to parameterize questions with context or data to administer different versions of the questions efficiently.
This can be useful for comparing responses for different data, agents and models, and performing data labeling tasks.

We also show how to filter, sort, select and print components of the dataset of results.

To see examples of all EDSL question types, run the following code:

.. code-block:: python

    from edsl import Question

    Question.available()


Output:

.. code-block:: text 

    ['checkbox',
    'extract',
    'free_text',
    'functional',
    'likert_five',
    'linear_scale',
    'list',
    'multiple_choice',
    'numerical',
    'rank',
    'top_k',
    'yes_no']


Newly released language models are automatically added to EDSL when they become available. 
To see a current list of available models, run the following code:

.. code-block:: python

    from edsl import Model

    Model.available()


A complete list of available models will be displayed. (We do not print it here because it is long.)

Now let's create a survey with multiple questions, scenarios, agents and models, and inspect the results:

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
    │ claude-3-5-sonnet-20240620 │ reading  │ chef          │ 3     │ As a chef, I'm always reading cookbooks,        │
    │                            │          │               │       │ culinary magazines, and food blogs to stay      │
    │                            │          │               │       │ up-to-date with the latest trends and           │
    │                            │          │               │       │ techniques in the culinary world. Just          │
    │                            │          │               │       │ yesterday, I was poring over a new cookbook     │
    │                            │          │               │       │ featuring modern interpretations of classic     │
    │                            │          │               │       │ French cuisine. I was particularly interested   │
    │                            │          │               │       │ in a section on innovative sauces and           │
    │                            │          │               │       │ reductions. Reading about food is an essential  │
    │                            │          │               │       │ part of my professional development and helps   │
    │                            │          │               │       │ inspire new ideas for my own cooking. It's not  │
    │                            │          │               │       │ just about recipes, but also understanding      │
    │                            │          │               │       │ flavor combinations, plating techniques, and    │
    │                            │          │               │       │ the cultural significance of different dishes.  │
    ├────────────────────────────┼──────────┼───────────────┼───────┼─────────────────────────────────────────────────┤
    │ gpt-4o                     │ reading  │ chef          │ 4     │ The most recent time I was reading, I was       │
    │                            │          │               │       │ flipping through a cookbook that focuses on     │
    │                            │          │               │       │ Mediterranean cuisine. I was particularly       │
    │                            │          │               │       │ interested in a recipe for a traditional Greek  │
    │                            │          │               │       │ moussaka. The layers of eggplant, seasoned      │
    │                            │          │               │       │ ground meat, and creamy béchamel sauce sounded  │
    │                            │          │               │       │ divine. I was taking notes on the different     │
    │                            │          │               │       │ spices and techniques used, thinking about how  │
    │                            │          │               │       │ I could incorporate some of those flavors into  │
    │                            │          │               │       │ my own dishes. It was a delightful and          │
    │                            │          │               │       │ inspiring read!                                 │
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
    'comment.recent_comment',
    'generated_tokens.enjoy_generated_tokens',
    'generated_tokens.recent_generated_tokens',
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
    'raw_model_response.enjoy_cost',
    'raw_model_response.enjoy_one_usd_buys',
    'raw_model_response.enjoy_raw_model_response',
    'raw_model_response.recent_cost',
    'raw_model_response.recent_one_usd_buys',
    'raw_model_response.recent_raw_model_response',
    'scenario.activity']


The `Results` object also supports SQL-like queries:

.. code-block:: python

    # Execute an SQL-like query on the results
    results.sql("select * from self", shape="wide")


View this notebook at the Coop to see output: `Starter Tutorial <https://www.expectedparrot.com/content/ef05e6dd-c176-4812-8143-46141d7f1833>`_.

Learn more about working with results in the :ref:`results` section.



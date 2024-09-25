.. _starter_tutorial:

Starter Tutorial
================

This tutorial provides example code for basic features of `EDSL, an open-source Python library <https://pypi.org/project/edsl/>`_ for simulating surveys, experiments and other research using AI agents and large language models.

In the steps below we show how to construct and run a simple question in EDSL, and then how to design more complex surveys with AI agents and different language models.
We also demonstrate methods for applying logic and rules to surveys, piping answers and adding data to questions, and analyzing survey results as datasets.

You can also `view this notebook at the Coop <https://www.expectedparrot.com/content/c7001765-a312-4db4-9838-8e783a376039>`_.


Technical setup
---------------

Before running the code below, please ensure that you have completed technical steps for using EDSL:

1. Download the EDSL package. See :ref:`installation` instructions. 
2. Choose how you want to use EDSL:

    * Run surveys remotely on the Expected Parrot server by activating :ref:`remote_inference` at your :ref:`coop` account
    * Run surveys locally by storing your own :ref:`api_keys` for language models that you want to use with EDSL

If you encounter any issues or have questions, please email us at info@expectedparrot.com or post a question at our `Discord channel <https://discord.com/invite/mxAYkjfy9m>`_.


Example: Running a simple question
----------------------------------

EDSL comes with a `variety of question types <https://docs.expectedparrot.com/en/latest/questions.html>`_ that we can choose from based on the form of the response that we want to get back from a model.
To see a list of all question types:

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


We can see the components of a particular question type by importing the question type class and calling the `example` method on it:

.. code-block:: python

    from edsl import (
        # QuestionCheckBox,
        # QuestionExtract,
        # QuestionFreeText,
        # QuestionFunctional,
        # QuestionLikertFive,
        # QuestionLinearScale,
        # QuestionList,
        QuestionMultipleChoice,
        # QuestionNumerical,
        # QuestionRank,
        # QuestionTopK,
        # QuestionYesNo
    )

    q = QuestionMultipleChoice.example() # substitute any question type class name
    q


Output:

.. code-block:: python

    {
        "question_name": "how_feeling",
        "question_text": "How are you?",
        "question_options": [
            "Good",
            "Great",
            "OK",
            "Bad"
        ],
        "question_type": "multiple_choice"
    }


Here we create a simple multiple choice question:

.. code-block:: python

    from edsl import QuestionMultipleChoice

    q = QuestionMultipleChoice(
        question_name = "smallest_prime",
        question_text = "Which is the smallest prime number?",
        question_options = [0, 1, 2, 3]
    )


We can administer it to a language model by calling the run method:

.. code-block:: python

    results = q.run()


This generates a dataset of `Results` that we can readily access with `built-in methods for analysis <https://docs.expectedparrot.com/en/latest/results.html>`_. 
Here we inspect the response, together with the model that was used and the model's "comment" about its response--a field that is automatically added to all question types other than free text:

.. code-block:: python

    results.select("model", "smallest_prime", "smallest_prime_comment").print(format="rich")


Output:

.. code-block:: text

    ┏━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ model  ┃ answer          ┃ comment                                                                              ┃
    ┃ .model ┃ .smallest_prime ┃ .smallest_prime_comment                                                              ┃
    ┡━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ gpt-4o │ 2               │ The smallest prime number is 2 because a prime number is defined as a natural number │
    │        │                 │ greater than 1 that has no positive divisors other than 1 and itself. 2 is the only  │
    │        │                 │ even prime number.                                                                   │
    └────────┴─────────────────┴──────────────────────────────────────────────────────────────────────────────────────┘


The `Results` also include information about the question, model parameters, prompts, generated tokens and raw responses. 
To see a list of all the components:

.. code-block:: python

    results.columns


Output:

.. code_block:: python 

    ['agent.agent_instruction',
    'agent.agent_name',
    'answer.smallest_prime',
    'comment.smallest_prime_comment',
    'generated_tokens.smallest_prime_generated_tokens',
    'iteration.iteration',
    'model.frequency_penalty',
    'model.logprobs',
    'model.max_tokens',
    'model.model',
    'model.presence_penalty',
    'model.temperature',
    'model.top_logprobs',
    'model.top_p',
    'prompt.smallest_prime_system_prompt',
    'prompt.smallest_prime_user_prompt',
    'question_options.smallest_prime_question_options',
    'question_text.smallest_prime_question_text',
    'question_type.smallest_prime_question_type',
    'raw_model_response.smallest_prime_cost',
    'raw_model_response.smallest_prime_one_usd_buys',
    'raw_model_response.smallest_prime_raw_model_response']


Example: Conducting a survey with agents and models
---------------------------------------------------

In the next example we construct a more complex survey consisting of multiple questions, and design personas for AI agents to answer it.
Then we select specific language models to generate the answers.

We start by creating questions in different types and passing them to a `Survey`:

.. code-block:: python 

    from edsl import QuestionLinearScale, QuestionFreeText

    q_enjoy = QuestionLinearScale(
        question_name = "enjoy",
        question_text = "On a scale from 1 to 5, how much do you enjoy reading?",
        question_options = [1, 2, 3, 4, 5],
        option_labels = {1:"Not at all", 5:"Very much"}
    )

    q_favorite_place = QuestionFreeText(
        question_name = "favorite_place",
        question_text = "Describe your favorite place for reading."
    )


We construct a `Survey` by passing a list of questions:

.. code-block:: python

    from edsl import Survey

    survey = Survey(questions = [q_enjoy, q_favorite_place])


Agents
^^^^^^

An important feature of EDSL is the ability to create AI agents to answer questions.
This is done by passing dictionaries of relevant "traits" to `Agent` objects that are used by language models to generate responses.
Learn more about `designing agents <https://docs.expectedparrot.com/en/latest/agents.html>`_.

Here we construct several simple agent personas to use with our survey:

.. code-block:: python 

    from edsl import AgentList, Agent

    agents = AgentList(
        Agent(traits = {"persona":p}) for p in ["artist", "mechanic", "sailor"]
    )


Language models 
^^^^^^^^^^^^^^^

EDSL works with many popular large language models that we can select to use with a survey.
This makes it easy to compare responses among models in the results that are generated.

To see a current list of available models:

.. code-block:: python 

    from edsl import Model

    # Model.available() # uncomment this code and run it to see the list of available models


To check the default model that will be used if no models are specified for a survey (e.g., as in the first example above):

.. code-block:: python

    Model()


Output (may be different if the default model has changed):

.. code-block:: python

    {
        "model": "gpt-4o",
        "parameters": {
            "temperature": 0.5,
            "max_tokens": 1000,
            "top_p": 1,
            "frequency_penalty": 0,
            "presence_penalty": 0,
            "logprobs": false,
            "top_logprobs": 3
        }
    }


Here we select some models to use with our survey:

.. code-block:: python 

    from edsl import ModelList, Model

    models = ModelList(
        Model(m) for m in ["gpt-4o", "gemini-pro"]
)


Running a survey
^^^^^^^^^^^^^^^^

We add agents and models to a survey using the `by` method.
Then we administer a survey the same way that we do an individual question, by calling the `run` method on it:

.. code-block:: python

    results = survey.by(agents).by(models).run()

    (
        results
        .sort_by("persona", "model")
        .select("model", "persona", "enjoy", "favorite_place")
        .print(format="rich")
    )

Example output:

.. code-block:: text

    ┏━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ model      ┃ agent    ┃ answer ┃ answer                                                                         ┃
    ┃ .model     ┃ .persona ┃ .enjoy ┃ .favorite_place                                                                ┃
    ┡━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ gemini-pro │ artist   │ 5      │ In the realm of my creative sanctuary, where colors dance and inspiration      │
    │            │          │        │ flows, my favorite place for reading is a secluded corner of my bohemian       │
    │            │          │        │ studio.                                                                        │
    │            │          │        │                                                                                │
    │            │          │        │ Amidst the canvases, paintbrushes, and the gentle hum of classical music, I    │
    │            │          │        │ find solace in a cozy armchair draped in vibrant fabrics. The walls are        │
    │            │          │        │ adorned with abstract prints and sketches, each a testament to my artistic     │
    │            │          │        │ journey.                                                                       │
    │            │          │        │                                                                                │
    │            │          │        │ The soft glow of natural light filters through the skylight, casting a warm    │
    │            │          │        │ ambiance upon the pages. With a steaming cup of freshly brewed coffee in hand, │
    │            │          │        │ I lose myself in the written words. The scent of paint and turpentine mingles  │
    │            │          │        │ with the aroma of the coffee, creating a symphony of sensory delights.         │
    │            │          │        │                                                                                │
    │            │          │        │ In this intimate space, I am surrounded by the fruits of my creativity and the │
    │            │          │        │ muses that inspire me. The books I read become a kaleidoscope of ideas,        │
    │            │          │        │ colors, and emotions that ignite my imagination and fuel my artistic           │
    │            │          │        │ endeavors.                                                                     │
    ├────────────┼──────────┼────────┼────────────────────────────────────────────────────────────────────────────────┤
    │ gpt-4o     │ artist   │ 4      │ My favorite place for reading is a cozy nook in my studio, where the sunlight  │
    │            │          │        │ streams through large windows, casting a warm glow on everything. There's a    │
    │            │          │        │ plush armchair draped with a soft, colorful throw, and a small wooden table    │
    │            │          │        │ beside it that holds a steaming cup of tea and a stack of books. The walls are │
    │            │          │        │ adorned with my artwork, creating an inspiring atmosphere. The gentle hum of   │
    │            │          │        │ classical music in the background adds to the serene ambiance, making it the   │
    │            │          │        │ perfect spot to lose myself in a good book.                                    │
    ├────────────┼──────────┼────────┼────────────────────────────────────────────────────────────────────────────────┤
    │ gemini-pro │ mechanic │ 4      │ Well, I'm more of a hands-on kind of guy, but when I do get some time to crack │
    │            │          │        │ open a book, there's no place I'd rather be than in my garage. The smell of    │
    │            │          │        │ oil and grease might not be everyone's cup of tea, but it's like a warm        │
    │            │          │        │ blanket to me.                                                                 │
    │            │          │        │                                                                                │
    │            │          │        │ I've got a comfy old recliner set up in the corner, right next to the window.  │
    │            │          │        │ I can prop my feet up on the toolbox and just get lost in a good story. The    │
    │            │          │        │ natural light is perfect for reading, and the gentle hum of the machinery in   │
    │            │          │        │ the background creates a soothing ambiance.                                    │
    ├────────────┼──────────┼────────┼────────────────────────────────────────────────────────────────────────────────┤
    │ gpt-4o     │ mechanic │ 3      │ My favorite place for reading is actually in my garage. I know it might sound  │
    │            │          │        │ a bit unconventional, but there's something about the smell of motor oil and   │
    │            │          │        │ the quiet hum of tools that makes it the perfect spot for me. I've got a cozy  │
    │            │          │        │ corner set up with an old recliner and a good lamp. When I'm not working on    │
    │            │          │        │ cars, I like to unwind there with a good book. The peace and quiet of the      │
    │            │          │        │ garage, combined with the familiar surroundings, really helps me focus and     │
    │            │          │        │ enjoy my reading time.                                                         │
    ├────────────┼──────────┼────────┼────────────────────────────────────────────────────────────────────────────────┤
    │ gemini-pro │ sailor   │ 5      │ Ahoy there, matey! My favorite place for reading is on the deck of me ship,    │
    │            │          │        │ with the wind in me hair and the sound of the waves crashing against the hull. │
    │            │          │        │ There's nothing like a good book to help me escape the perils of the high seas │
    │            │          │        │ and dream of far-off lands.                                                    │
    ├────────────┼──────────┼────────┼────────────────────────────────────────────────────────────────────────────────┤
    │ gpt-4o     │ sailor   │ 4      │ Ah, matey, my favorite place for reading be the deck of me ship, just as the   │
    │            │          │        │ sun be setting on the horizon. There's a gentle sway to the vessel, and the    │
    │            │          │        │ salty sea breeze carries the scent of adventure. I settle into a sturdy wooden │
    │            │          │        │ chair, the creak of the timbers beneath me a familiar comfort. The sound of    │
    │            │          │        │ the waves lapping against the hull and the distant call of seabirds be the     │
    │            │          │        │ perfect background music. With a lantern casting a warm, golden glow over the  │
    │            │          │        │ pages, I lose meself in tales of distant lands and daring escapades. 'Tis a    │
    │            │          │        │ place where the sea and stories become one, and I feel truly at home.          │
    └────────────┴──────────┴────────┴────────────────────────────────────────────────────────────────────────────────┘


Example: Adding context to questions
------------------------------------

EDSL provides a variety of ways to add data or content to survey questions. 
These methods include:

* `Piping <https://docs.expectedparrot.com/en/latest/surveys.html#id2>`_ answers to questions into follow-on questions
* `Adding "memory" <https://docs.expectedparrot.com/en/latest/surveys.html#question-memory>`_ of prior questions and answers in a survey when presenting other questions to a model
* `Parameterizing questions with data <https://docs.expectedparrot.com/en/latest/scenarios.html>`_, e.g., content from PDFs, CSVs, docs, images or other sources that you want to add to questions

Piping question answers
^^^^^^^^^^^^^^^^^^^^^^^

Here we demonstrate how to pipe the answer to a question into the text of another question.
This is done by using a placeholder `{{ <question_name>.answer }}` in the text of the follow-on question where the answer to the prior question is to be inserted when the survey is run.
This causes the questions to be administered in the required order (survey questions are administered asynchronously by default).
Learn more about `piping question answers <https://docs.expectedparrot.com/en/latest/surveys.html#id2>`_.

Here we insert the answer to a numerical question into the text of a follow-on yes/no question:

.. code-block:: python 

    from edsl import QuestionNumerical, QuestionYesNo, Survey

    q1 = QuestionNumerical(
        question_name = "random_number",
        question_text = "Pick a random number between 1 and 1,000."
    )

    q2 = QuestionYesNo(
        question_name = "prime",
        question_text = "Is this a prime number: {{ random_number.answer }}"
    )

    survey = Survey([q1, q2])

    results = survey.run()


We can check the `user_prompt` for the `prime` question to verify that that the answer to the `random_number` question was piped into it:

.. code-block:: python

    results.select("random_number", "prime_user_prompt", "prime", "prime_comment").print(format="rich")


Example output:

.. code-block:: text

    ┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ answer         ┃ prompt                                    ┃ answer ┃ comment                                   ┃
    ┃ .random_number ┃ .prime_user_prompt                        ┃ .prime ┃ .prime_comment                            ┃
    ┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ 728            │                                           │ No     │ 728 is not a prime number because it has  │
    │                │ Is this a prime number: 728               │        │ divisors other than 1 and itself. For     │
    │                │                                           │        │ example, it is divisible by 2 (728 ÷ 2 =  │
    │                │                                           │        │ 364).                                     │
    │                │ No                                        │        │                                           │
    │                │                                           │        │                                           │
    │                │ Yes                                       │        │                                           │
    │                │                                           │        │                                           │
    │                │                                           │        │                                           │
    │                │ Only 1 option may be selected.            │        │                                           │
    │                │ Please reponse with just your answer.     │        │                                           │
    │                │                                           │        │                                           │
    │                │                                           │        │                                           │
    │                │ After the answer, you can put a comment   │        │                                           │
    │                │ explaining your reponse.                  │        │                                           │
    └────────────────┴───────────────────────────────────────────┴────────┴───────────────────────────────────────────┘


Adding "memory" of questions and answers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Here we instead add a "memory" of the first question and answer to the context of the second question.
This is done by calling a memory rule and identifying the question(s) to add.
Instead of just the answer, information about the full question and answer are presented with the follow-on question text, and no placeholder is used.
Learn more about `question memory rules <https://docs.expectedparrot.com/en/latest/surveys.html#survey-rules-logic>`_.

Here we demonstrate the `add_targeted_memory` method (we could also use `set_full_memory_mode` or other memory rules):

.. code-block:: python 

    from edsl import QuestionNumerical, QuestionYesNo, Survey

    q1 = QuestionNumerical(
        question_name = "random_number",
        question_text = "Pick a random number between 1 and 1,000."
    )

    q2 = QuestionYesNo(
        question_name = "prime",
        question_text = "Is the number you picked a prime number?"
    )

    survey = Survey([q1, q2]).add_targeted_memory(q2, q1)

    results = survey.run()


We can again use the `user_prompt` to verify the context that was added to the follow-on question:

.. code-block:: python

    results.select("random_number", "prime_user_prompt", "prime", "prime_comment").print(format="rich")


Example output:

.. code-block:: text

    ┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ answer         ┃ prompt                                    ┃ answer ┃ comment                                   ┃
    ┃ .random_number ┃ .prime_user_prompt                        ┃ .prime ┃ .prime_comment                            ┃
    ┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ 728            │                                           │ No     │ 728 is not a prime number because it can  │
    │                │ Is the number you picked a prime number?  │        │ be divided by numbers other than 1 and    │
    │                │                                           │        │ itself, such as 2, 4, 8, 91, and 182.     │
    │                │                                           │        │                                           │
    │                │ No                                        │        │                                           │
    │                │                                           │        │                                           │
    │                │ Yes                                       │        │                                           │
    │                │                                           │        │                                           │
    │                │                                           │        │                                           │
    │                │ Only 1 option may be selected.            │        │                                           │
    │                │ Please reponse with just your answer.     │        │                                           │
    │                │                                           │        │                                           │
    │                │                                           │        │                                           │
    │                │ After the answer, you can put a comment   │        │                                           │
    │                │ explaining your reponse.                  │        │                                           │
    │                │         Before the question you are now   │        │                                           │
    │                │ answering, you already answered the       │        │                                           │
    │                │ following question(s):                    │        │                                           │
    │                │                 Question: Pick a random   │        │                                           │
    │                │ number between 1 and 1,000.               │        │                                           │
    │                │         Answer: 728                       │        │                                           │
    └────────────────┴───────────────────────────────────────────┴────────┴───────────────────────────────────────────┘


Scenarios
---------

We can also add external data or content to survey questions.
This can be useful when you want to efficiently create and administer multiple versions of questions at once, e.g., for conducting data labeling tasks.
This is done by creating `Scenario` dictionaries for the data or content to be used with a survey, where the keys match `{{ placeholder }}` names used in question texts (or question options) and the values are the content to be added.
Scenarios can also be used to `add metadata to survey results <https://docs.expectedparrot.com/en/latest/notebooks/adding_metadata.html>`_, e.g., data sources or other information that you may want to include in the results for reference but not necessarily include in question texts.

In the next example we revise the prior survey questions about reading to take a parameter for other activities that we may want to add to the questions, and create simple scenarios for some activities.
EDSL provides methods for automatically generating scenarios from a variety of data sources, including PDFs, CSVs, docs, images, tables and dicts. 
We use the `from_list` method to convert a list of activities into scenarios.

Then we demonstrate how to use scenarios to create multiple versions of our questions either (i) when constructing a survey or (ii) when running it:

* In the latter case, the `by` method is used to add scenarios to a survey of questions with placeholders at the time that it is run (the same way that agents and models are added to a survey). This adds a `scenario` column to the results with a row for each answer to each question for each scenario.
* In the former case, the `loop` method is used to create a list of versions of a question with the scenarios already added to it; when the questions are passed to a survey and it is run, the results include columns for each individual question; there is no `scenario` column and a single row for each agent's answers to all the questions.

Learn more about `using scenarios <https://docs.expectedparrot.com/en/latest/scenarios.html>`_.

Here we create simple scenarios for a list of activities:

.. code-block:: python 

    from edsl import ScenarioList, Scenario

    scenarios = ScenarioList.from_list("activity", ["reading", "running", "relaxing"])  


Adding scenarios using the `by` method
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Here we add the scenarios to the survey when we run it, together with any desired agents and models:

.. code-block:: python

    from edsl import QuestionLinearScale, QuestionFreeText, Survey

    q_enjoy = QuestionLinearScale(
        question_name = "enjoy",
        question_text = "On a scale from 1 to 5, how much do you enjoy {{ activity }}?",
        question_options = [1, 2, 3, 4, 5],
        option_labels = {1:"Not at all", 5:"Very much"}
    )

    q_favorite_place = QuestionFreeText(
        question_name = "favorite_place",
        question_text = "In a brief sentence, describe your favorite place for {{ activity }}."
    )

    survey = Survey([q_enjoy, q_favorite_place])

    results = survey.by(scenarios).by(agents).by(models).run()

    (
        results
        .filter("model.model == 'gpt-4o'")
        .sort_by("activity", "persona")
        .select("activity", "persona", "enjoy", "favorite_place")
        .print(format="rich")
    )


Example output:

.. code-block:: text 

    ┏━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ scenario  ┃ agent    ┃ answer ┃ answer                                                                          ┃
    ┃ .activity ┃ .persona ┃ .enjoy ┃ .favorite_place                                                                 ┃
    ┡━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ reading   │ artist   │ 4      │ My favorite place for reading is a cozy nook by a large window, where the       │
    │           │          │        │ natural light illuminates the pages and I can occasionally glance outside for   │
    │           │          │        │ inspiration.                                                                    │
    ├───────────┼──────────┼────────┼─────────────────────────────────────────────────────────────────────────────────┤
    │ reading   │ mechanic │ 3      │ My favorite place for reading is in my garage, surrounded by tools and the      │
    │           │          │        │ scent of motor oil, where it's quiet and I can focus.                           │
    ├───────────┼──────────┼────────┼─────────────────────────────────────────────────────────────────────────────────┤
    │ reading   │ sailor   │ 4      │ My favorite place for reading is the ship's deck at dawn, with the gentle       │
    │           │          │        │ rocking of the waves and the salty sea breeze in the air.                       │
    ├───────────┼──────────┼────────┼─────────────────────────────────────────────────────────────────────────────────┤
    │ relaxing  │ artist   │ 4      │ My favorite place for relaxing is a cozy nook in my art studio, surrounded by   │
    │           │          │        │ my paintings and the soft glow of natural light streaming through the windows.  │
    ├───────────┼──────────┼────────┼─────────────────────────────────────────────────────────────────────────────────┤
    │ relaxing  │ mechanic │ 3      │ My favorite place for relaxing is my garage, where I can tinker with cars and   │
    │           │          │        │ unwind with the smell of motor oil and the sound of tools.                      │
    ├───────────┼──────────┼────────┼─────────────────────────────────────────────────────────────────────────────────┤
    │ relaxing  │ sailor   │ 3      │ My favorite place for relaxing is on the deck of my boat, anchored in a quiet   │
    │           │          │        │ cove with the gentle rocking of the waves and the sound of the sea around me.   │
    ├───────────┼──────────┼────────┼─────────────────────────────────────────────────────────────────────────────────┤
    │ running   │ artist   │ 1      │ My favorite place for running is a serene forest trail, where the dappled       │
    │           │          │        │ sunlight filters through the leaves and the air is filled with the scent of     │
    │           │          │        │ pine and earth.                                                                 │
    ├───────────┼──────────┼────────┼─────────────────────────────────────────────────────────────────────────────────┤
    │ running   │ mechanic │ 1      │ My favorite place for running is a scenic trail through the woods, where the    │
    │           │          │        │ air is fresh and the sounds of nature keep me company.                          │
    ├───────────┼──────────┼────────┼─────────────────────────────────────────────────────────────────────────────────┤
    │ running   │ sailor   │ 3      │ My favorite place for running is along the rugged coastline at dawn, where the  │
    │           │          │        │ salty sea breeze and crashing waves keep me company.                            │
    └───────────┴──────────┴────────┴─────────────────────────────────────────────────────────────────────────────────┘


Adding scenarios using the `loop` method
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Here we add scenarios to questions when constructing a survey, as opposed to when running it.
When we run the survey the results will include columns for each question and no `scenario` field. 
Note that we can also optionally use the scenario key in the question names (they are otherwise incremented by default):

.. code-block:: python

    from edsl import QuestionLinearScale, QuestionFreeText

    q_enjoy = QuestionLinearScale(
        question_name = "enjoy_{{ activity }}", # optional use of scenario key
        question_text = "On a scale from 1 to 5, how much do you enjoy {{ activity }}?",
        question_options = [1, 2, 3, 4, 5],
        option_labels = {1:"Not at all", 5:"Very much"}
    )

    q_favorite_place = QuestionFreeText(
        question_name = "favorite_place_{{ activity }}", # optional use of scenario key
        question_text = "In a brief sentence, describe your favorite place for {{ activity }}."
    )


Looping the scenarios to create a lists of versions of the `enjoy` question:

.. code-block:: python 

    enjoy_questions = q_enjoy.loop(scenarios)
    enjoy_questions


Output:

.. code_block:: python 

    [Question('linear_scale', question_name = """enjoy_reading""", question_text = """On a scale from 1 to 5, how much do you enjoy reading?""", question_options = [1, 2, 3, 4, 5], option_labels = {1: 'Not at all', 5: 'Very much'}),
    Question('linear_scale', question_name = """enjoy_running""", question_text = """On a scale from 1 to 5, how much do you enjoy running?""", question_options = [1, 2, 3, 4, 5], option_labels = {1: 'Not at all', 5: 'Very much'}),
    Question('linear_scale', question_name = """enjoy_relaxing""", question_text = """On a scale from 1 to 5, how much do you enjoy relaxing?""", question_options = [1, 2, 3, 4, 5], option_labels = {1: 'Not at all', 5: 'Very much'})]


Looping the scenarios to create a lists of versions of the `favorite_place` question:

.. code-block:: python 

    favorite_place_questions = q_favorite_place.loop(scenarios)
    favorite_place_questions


Output:

.. code-block:: python 

    [Question('free_text', question_name = """favorite_place_reading""", question_text = """In a brief sentence, describe your favorite place for reading."""),
    Question('free_text', question_name = """favorite_place_running""", question_text = """In a brief sentence, describe your favorite place for running."""),
    Question('free_text', question_name = """favorite_place_relaxing""", question_text = """In a brief sentence, describe your favorite place for relaxing.""")]


Combining the questions into a survey and running it:

.. code-block:: python 

    survey = Survey(questions = enjoy_questions + favorite_place_questions)

    results = survey.by(agents).by(models).run()

    # results.columns # see that there are additional question fields and no scenario field

    (
        results
        .filter("model.model == 'gpt-4o'")
        .sort_by("persona")
        .select("persona", "enjoy_reading", "enjoy_running", "enjoy_relaxing", "favorite_place_reading", "favorite_place_running", "favorite_place_relaxing")
        .print(format="rich")
    )


Example output:

.. code-block:: text 

    ┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
    ┃ agent    ┃ answer         ┃ answer         ┃ answer         ┃ answer         ┃ answer          ┃ answer         ┃
    ┃ .persona ┃ .enjoy_reading ┃ .enjoy_running ┃ .enjoy_relaxi… ┃ .favorite_pla… ┃ .favorite_plac… ┃ .favorite_pla… ┃
    ┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
    │ artist   │ 4              │ 1              │ 4              │ My favorite    │ My favorite     │ My favorite    │
    │          │                │                │                │ place for      │ place for       │ place for      │
    │          │                │                │                │ reading is a   │ running is a    │ relaxing is a  │
    │          │                │                │                │ cozy nook by a │ serene forest   │ cozy nook in   │
    │          │                │                │                │ large window,  │ trail, where    │ my art studio, │
    │          │                │                │                │ where the      │ the dappled     │ surrounded by  │
    │          │                │                │                │ natural light  │ sunlight        │ my paintings   │
    │          │                │                │                │ illuminates    │ filters through │ and the soft   │
    │          │                │                │                │ the pages and  │ the leaves and  │ glow of        │
    │          │                │                │                │ I can          │ the air is      │ natural light  │
    │          │                │                │                │ occasionally   │ filled with the │ streaming      │
    │          │                │                │                │ glance outside │ scent of pine   │ through the    │
    │          │                │                │                │ for            │ and earth.      │ windows.       │
    │          │                │                │                │ inspiration.   │                 │                │
    ├──────────┼────────────────┼────────────────┼────────────────┼────────────────┼─────────────────┼────────────────┤
    │ mechanic │ 3              │ 1              │ 3              │ My favorite    │ My favorite     │ My favorite    │
    │          │                │                │                │ place for      │ place for       │ place for      │
    │          │                │                │                │ reading is in  │ running is a    │ relaxing is my │
    │          │                │                │                │ my garage,     │ scenic trail    │ garage, where  │
    │          │                │                │                │ surrounded by  │ through the     │ I can tinker   │
    │          │                │                │                │ tools and the  │ woods, where    │ with cars and  │
    │          │                │                │                │ scent of motor │ the air is      │ unwind with    │
    │          │                │                │                │ oil, where     │ fresh and the   │ the smell of   │
    │          │                │                │                │ it's quiet and │ sounds of       │ motor oil and  │
    │          │                │                │                │ I can focus.   │ nature keep me  │ the sound of   │
    │          │                │                │                │                │ company.        │ tools.         │
    ├──────────┼────────────────┼────────────────┼────────────────┼────────────────┼─────────────────┼────────────────┤
    │ sailor   │ 4              │ 3              │ 3              │ My favorite    │ My favorite     │ My favorite    │
    │          │                │                │                │ place for      │ place for       │ place for      │
    │          │                │                │                │ reading is the │ running is      │ relaxing is on │
    │          │                │                │                │ ship's deck at │ along the       │ the deck of my │
    │          │                │                │                │ dawn, with the │ rugged          │ boat, anchored │
    │          │                │                │                │ gentle rocking │ coastline at    │ in a quiet     │
    │          │                │                │                │ of the waves   │ dawn, where the │ cove with the  │
    │          │                │                │                │ and the salty  │ salty sea       │ gentle rocking │
    │          │                │                │                │ sea breeze in  │ breeze and      │ of the waves   │
    │          │                │                │                │ the air.       │ crashing waves  │ and the sound  │
    │          │                │                │                │                │ keep me         │ of the sea     │
    │          │                │                │                │                │ company.        │ around me.     │
    └──────────┴────────────────┴────────────────┴────────────────┴────────────────┴─────────────────┴────────────────┘


Exploring `Results`
-------------------

EDSL comes with `built-in methods for analyzing and visualizing survey results <https://docs.expectedparrot.com/en/latest/language_models.html>`_. 
For example, you can call the `to_pandas` method to convert results into a dataframe:

.. code-block:: python 
    
    df = results.to_pandas(remove_prefix=True)
    # df


The `Results` object also supports SQL-like queries with the the `sql` method:

.. code-block:: python 

    results.sql("""
    select model, persona, enjoy_reading, favorite_place_reading
    from self
    order by 1,2,3
    """, shape="wide")


Output:

.. code-block:: text 

        model	    persona	    enjoy_reading	favorite_place_reading
    0	gemini-pro	artist	    5	            My heart finds solace in the hushed, sun-drenc...
    1	gemini-pro	mechanic	4	            My favorite place to read is in my garage, sur...
    2	gemini-pro	sailor	    5	            My favorite place for reading is the bow of th...
    3	gpt-4o	    artist	    4	            My favorite place for reading is a cozy nook b...
    4	gpt-4o	    mechanic	3	            My favorite place for reading is in my garage,...
    5	gpt-4o	    sailor	    4	            My favorite place for reading is the ship's de...


Posting to the Coop
-------------------

The `Coop <https://www.expectedparrot.com/explore>`_ is a platform for creating, storing and sharing LLM-based research.
It is fully integrated with EDSL and accessible from your workspace or Coop account page.
Learn more about `creating an account <https://www.expectedparrot.com/login>`_ and `using the Coop <https://docs.expectedparrot.com/en/latest/coop.html>`_.

We can post any EDSL object to the Coop by call the `push` method on it, optionally passing a `description` and `visibility` status:

.. code-block:: python 

    results.push(description = "Starter tutorial sample survey results", visibility="public")


Example output:

.. code-block:: python 

    {'description': 'Starter tutorial sample survey results',
    'object_type': 'results',
    'url': 'https://www.expectedparrot.com/content/c7001765-a312-4db4-9838-8e783a376039',
    'uuid': 'c7001765-a312-4db4-9838-8e783a376039',
    'version': '0.1.33.dev1',
    'visibility': 'public'}


To post a notebook:

.. code-block:: python 

    from edsl import Notebook

    notebook = Notebook(path="filename.ipynb")

    notebook.push(description="Starter Tutorial", visibility="public")


You can view and download a notebook for this tutorial at the Coop `here <https://www.expectedparrot.com/content/2d0c7905-933c-441a-8203-741d9dd942c9>`_.
.. _questions:

Questions
=========

.. This module contains the Question class, which is the base class for all questions in EDSL.

EDSL includes templates for many common question types, including multiple choice, checkbox, free text, numerical, linear scale, Likert scale and others.
The `Question` class has subclasses for each of these types (`QuestionMultipleChoice`, `QuestionFreeText`, etc.) which have methods for validating answers and responses from language models.


Question type templates 
-----------------------
Each question type requires a `question_name` and `question_text`. 
The `question_name` is a unique Pythonic identifier for a question (e.g., "favorite_color" but not "favorite color").
The `question_text` is the text of the question itself written as a string (e.g., "What is your favorite color?").

Individual question types other than free text also require certain additional fields.
For example, multiple choice, checkbox, linear scale, rank, top k and budget questions all require a `question_options` list of available answer options.
See examples below for details on required fields and formatting for each type.


Constructing a question
-----------------------
To construct a question, we start by importing the appropriate question type for the desired result. 
For example, if we want the response to be a single option selected from a given list we can create a multiple choice question:

.. code-block:: python

   from edsl import QuestionMultipleChoice

Next we format a question in the question type template. 
A multiple choice question requires a question name, question text and list of question options:

.. code-block:: python

   q = QuestionMultipleChoice(
      question_name = "favorite_primary_color",
      question_text = "Which is your favorite primary color?",
      question_options = ["red", "yellow", "blue"] 
   )

Details and examples of each question type can be found at the bottom of this page.


Creating a survey
-----------------
We can combine questions into a survey by passing a list of questions to a `Survey` object:

.. code-block:: python 

   from edsl.questions import QuestionFreeText
   from edsl import Survey 

   q1 = QuestionFreeText(
      question_name = "favorite_color",
      question_text = "Which is your favorite color?"
   )
   q2 = QuestionFreeText(
      question_name = "favorite_pet",
      question_text = "Which is your favorite pet?"
   )
   q3 = QuestionFreeText(
      question_name = "favorite_movie",
      question_text = "Which is your favorite movie?"
   )

   survey = Survey(questions = [q1, q2, q3])

This allows us to administer multiple questions at once, either asynchronously (by default) or according to specified logic (e.g., skip or stop rules).
To learn more about designing surveys with conditional logic, please see the :ref:`surveys` section.


Simulating a response 
---------------------
We generate a response to a question by delivering it to a language model.
This is done by calling the `run` method for the question:

.. code-block:: python

   results = q.run()

This will generate a `Results` object that contains a single `Result` representing the response to the question and information about the model used.
If the model to be used has not been specified (as in the above example), the `run` method delivers the question to the default LLM (GPT 4).
We can inspect the response and model used by calling the `select` and `print` methods on the components of the results that we want to display.
For example, we can print just the `answer` to the question:

.. code-block:: python 

   results.select("answer.favorite_primary_color").print()

Output:

.. code-block::

   blue

Or to inspect the model:

.. code-block:: python 

   results.select("model").print()

Output: 

.. code-block::

   gpt-4-1106-preview

If questions have been combined in a survey, the `run` method is called directly on the survey instead:

.. code-block:: python

   results = survey.run()

For a survey, each `Result` represents a response for the set of survey questions. 
To learn more about analyzing results, please see the :ref:`results` section.


Parameterizing a question
-------------------------
A question can also be constructed to take one or more parameters that are replaced with specified values when the question is run.
This allows us to easily create and administer multiple versions of a question at once.

*Key steps*:

Create a question text that takes a parameter in double braces:

.. code-block:: python

   from edsl.questions import QuestionFreeText

   q = QuestionFreeText(
      question_name = "favorite_item",
      question_text = "What is your favorite {{ item }}?",
   )

Create a dictionary for each value that will replace the parameter and store them in `Scenario` objects:

.. code-block:: python

   from edsl import Scenario 

   scenarios = [Scenario({"item": item}) for item in ["color", "food"]]

Pass the scenario or scenarios to the question with the `by` method when the question is run. 
If multiple scenarios are to be used, they are passed as a list:

.. code-block:: python 

   results = q.by(scenarios).run()

The `Results` that are generated will include an individual `Result` for each version of the question that was answered.
Scenarios can also be passed to a survey of questions in the same way:

.. code-block:: python 

   results = survey.by(scenarios).run()

This will generate `Results` where each `Result` includes responses for all the scenarios of each question in the survey.
To learn more about using scenarios, please see the :ref:`Scenarios` section.


Designing AI agents 
-------------------
A key feature of EDSL is the ability to design AI agents with personas and other traits for language models to use in responding to questions.
The use of agents allows us to simulate survey results for target audiences at scale.
This is done by creating `Agent` objects with dictionaries of desired traits and adding them to questions when they are run.
For example, if we want a question answered by an AI agent representing a student we can create an `Agent` object with a relevant persona and attributes:

.. code-block:: python

   from edsl import Agent

   agent = Agent(traits = {
      "persona": "You are a student...", # can be an extended text
      "age": 20, # individual trait values can be useful for analysis
      "current_grade": "college sophomore"
      })


To generate a response for the agent, we pass it to the `by` method when we run the question:

.. code-block:: python 

   results = q.by(agent).run()

If we have multiple agents, we pass them as a list:

.. code-block:: python 

   results = q.by(agents).run()

The `Results` will contain a `Result` for each agent that answered the question.
To learn more about designing agents, please see the :ref:`agents` section.


Specifying language models
--------------------------
In the above examples we did not specify a language model for the question or survey, so the default model (GPT 4) was used.
Similar to the way that we optionally passed scenarios to a question and added AI agents, we can also use the `by` method to specify one or more LLMs to use in generating results.
This is done by creating `Model` objects for desired models and optionally specifying model parameters, such as temperature.

To check available models:

.. code-block:: python

   from edsl import Model

   Model.available()

This will return a list of names of models that we can choose from:

.. code-block:: python

   [['01-ai/Yi-34B-Chat', 'deep_infra', 0],
   ['Austism/chronos-hermes-13b-v2', 'deep_infra', 1],
   ['Gryphe/MythoMax-L2-13b', 'deep_infra', 2],
   ['Gryphe/MythoMax-L2-13b-turbo', 'deep_infra', 3],
   ['HuggingFaceH4/zephyr-orpo-141b-A35b-v0.1', 'deep_infra', 4],
   ['Phind/Phind-CodeLlama-34B-v2', 'deep_infra', 5],
   ['bigcode/starcoder2-15b', 'deep_infra', 6],
   ['bigcode/starcoder2-15b-instruct-v0.1', 'deep_infra', 7],
   ['claude-3-haiku-20240307', 'anthropic', 8],
   ['claude-3-opus-20240229', 'anthropic', 9],
   ['claude-3-sonnet-20240229', 'anthropic', 10],
   ['codellama/CodeLlama-34b-Instruct-hf', 'deep_infra', 11],
   ['codellama/CodeLlama-70b-Instruct-hf', 'deep_infra', 12],
   ['cognitivecomputations/dolphin-2.6-mixtral-8x7b', 'deep_infra', 13],
   ['databricks/dbrx-instruct', 'deep_infra', 14],
   ['deepinfra/airoboros-70b', 'deep_infra', 15],
   ['gemini-pro', 'google', 16],
   ['google/codegemma-7b-it', 'deep_infra', 17],
   ['google/gemma-1.1-7b-it', 'deep_infra', 18],
   ['gpt-3.5-turbo', 'openai', 19],
   ['gpt-3.5-turbo-0125', 'openai', 20],
   ['gpt-3.5-turbo-0301', 'openai', 21],
   ['gpt-3.5-turbo-0613', 'openai', 22],
   ['gpt-3.5-turbo-1106', 'openai', 23],
   ['gpt-3.5-turbo-16k', 'openai', 24],
   ['gpt-3.5-turbo-16k-0613', 'openai', 25],
   ['gpt-3.5-turbo-instruct', 'openai', 26],
   ['gpt-3.5-turbo-instruct-0914', 'openai', 27],
   ['gpt-4', 'openai', 28],
   ['gpt-4-0125-preview', 'openai', 29],
   ['gpt-4-0613', 'openai', 30],
   ['gpt-4-1106-preview', 'openai', 31],
   ['gpt-4-1106-vision-preview', 'openai', 32],
   ['gpt-4-turbo', 'openai', 33],
   ['gpt-4-turbo-2024-04-09', 'openai', 34],
   ['gpt-4-turbo-preview', 'openai', 35],
   ['gpt-4-vision-preview', 'openai', 36],
   ['gpt-4o', 'openai', 37],
   ['gpt-4o-2024-05-13', 'openai', 38],
   ['lizpreciatior/lzlv_70b_fp16_hf', 'deep_infra', 39],
   ['llava-hf/llava-1.5-7b-hf', 'deep_infra', 40],
   ['meta-llama/Llama-2-13b-chat-hf', 'deep_infra', 41],
   ['meta-llama/Llama-2-70b-chat-hf', 'deep_infra', 42],
   ['meta-llama/Llama-2-7b-chat-hf', 'deep_infra', 43],
   ['meta-llama/Meta-Llama-3-70B-Instruct', 'deep_infra', 44],
   ['meta-llama/Meta-Llama-3-8B-Instruct', 'deep_infra', 45],
   ['microsoft/WizardLM-2-7B', 'deep_infra', 46],
   ['microsoft/WizardLM-2-8x22B', 'deep_infra', 47],
   ['mistralai/Mistral-7B-Instruct-v0.1', 'deep_infra', 48],
   ['mistralai/Mistral-7B-Instruct-v0.2', 'deep_infra', 49],
   ['mistralai/Mixtral-8x22B-Instruct-v0.1', 'deep_infra', 50],
   ['mistralai/Mixtral-8x22B-v0.1', 'deep_infra', 51],
   ['mistralai/Mixtral-8x7B-Instruct-v0.1', 'deep_infra', 52],
   ['openchat/openchat_3.5', 'deep_infra', 53]]
   

We can also check the models for which we have already added API keys:

.. code-block:: python 

   Model.check_models()

(See instructions on storing :ref:`api_keys` for the models that you want to use in your `.env` file.)

To specify models for a survey we first create `Model` objects:

.. code-block:: python

   models = [Model(model) for model in ['claude-3-opus-20240229', 'llama-2-70b-chat-hf']]

Then we add them to a question or survey with the `by` method when running it:

.. code-block:: python 

   results = q.by(models).run()

If scenarios and/or agents are also specified, each component is added in its own `by` call, chained together in any order, with the `run` method appended last:

.. code-block:: python 

   results = q.by(scenarios).by(agents).by(models).run()

Note that multiple scenarios, agents and models are always passed as lists in the same `by` call.

Learn more about specifying question scenarios, agents and language models and their parameters in the respective sections:

* :ref:`scenarios`
* :ref:`agents`
* :ref:`language_models`


.. QuestionBase class 
.. ------------------

.. .. automodule:: edsl.questions.QuestionBase
..    :members:
..    :undoc-members:
..    :show-inheritance:
..    :special-members: __init__
..    :exclude-members: question_name, question_text, question_type, short_names_dict, main


Question type classes
---------------------

QuestionMultipleChoice class
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
A subclass of the `Question` class for creating multiple choice questions where the response is a single option selected from a list of options.
It specially requires a `question_options` list of strings for the options.
Example usage:

.. code-block:: python

   from edsl.questions import QuestionMultipleChoice

   q = QuestionMultipleChoice(
      question_name = "color",
      question_text = "What is your favorite color?",
      question_options = ["Red", "Blue", "Green", "Yellow"]
   )

An example can also created using the `example` method:

.. code-block:: python

   QuestionMultipleChoice.example()


.. automodule:: edsl.questions.QuestionMultipleChoice
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: purpose, question_type, question_options, main
   

QuestionCheckBox class
^^^^^^^^^^^^^^^^^^^^^^
A subclass of the `Question` class for creating questions where the response is a list of one or more of the given options.
It specially requires a `question_options` list of strings for the options.
The minimum number of options that *must* be selected and the maximum number that *may* be selected can be specified when creating the question (parameters `min_selections` and `max_selections`). 
If not specified, the minimum number of options that must be selected is 1 and the maximum allowed is the number of question options provided.
Example usage:

.. code-block:: python

   from edsl.questions import QuestionCheckBox

   q = QuestionCheckBox(
      question_name = "favorite_days",
      question_text = "What are your 2 favorite days of the week?",
      question_options = ["Monday", "Tuesday", "Wednesday", 
      "Thursday", "Friday", "Saturday", "Sunday"],
      min_selections = 2, # optional
      max_selections = 2  # optional
   )

An example can also be created using the `example` method:

.. code-block:: python

   QuestionCheckBox.example()


.. automodule:: edsl.questions.QuestionCheckBox
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: purpose, question_type, question_options, min_selections, max_selections, main


QuestionFreeText class
^^^^^^^^^^^^^^^^^^^^^^
A subclass of the `Question` class for creating free response questions.
There are no specially required fields (only `question_name` and `question_text`).
The response is a single string of text.
Example usage:

.. code-block:: python

   from edsl.questions import QuestionFreeText

   q = QuestionFreeText(
      question_name = "food",
      question_text = "What is your favorite food?"
   )

An example can also be created using the `example` method:

.. code-block:: python

   QuestionFreeText.example()


.. automodule:: edsl.questions.QuestionFreeText
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: allow_nonresponse, default_instructions, question_type, main


QuestionLinearScale class
^^^^^^^^^^^^^^^^^^^^^^^^^
A subclass of the `QuestionMultipleChoice` class for creating linear scale questions.
It requires a `question_options` list of integers for the scale.
The `option_labels` parameter can be used to specify labels for the scale options.
Example usage:

.. code-block:: python

   from edsl.questions import QuestionLinearScale

   q = QuestionLinearScale(
      question_name = "studying",
      question_text = """On a scale from 0 to 5, how much do you 
      enjoy studying? (0 = not at all, 5 = very much)""",
      question_options = [0, 1, 2, 3, 4, 5], # integers
      option_labels = {0: "Not at all", 5: "Very much"} # optional
   )

An example can also be created using the `example` method:

.. code-block:: python

   QuestionLinearScale.example()


.. automodule:: edsl.questions.derived.QuestionLinearScale
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: question_type, question_options, option_labels, main


QuestionNumerical class
^^^^^^^^^^^^^^^^^^^^^^^
A subclass of the `Question` class for creating questions where the response is a numerical value.
The minimum and maximum values of the answer can be specified using the `min_value` and `max_value` parameters.
Example usage:

.. code-block:: python

   from edsl.questions import QuestionNumerical

   q = QuestionNumerical(
      question_name = "work_days",
      question_text = "How many days a week do you normally work?",
      min_value = 1, # optional
      max_value = 7  # optional
   )

An example can also be created using the `example` method:

.. code-block:: python

   QuestionNumerical.example()


.. automodule:: edsl.questions.QuestionNumerical
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: question_type, min_value, max_value, main


QuestionLikertFive class
^^^^^^^^^^^^^^^^^^^^^^^^
A subclass of the `QuestionMultipleChoice` class for creating questions where the answer is a response to a given statement on a 5-point Likert scale.
(The scale does *not* need to be added as a parameter.)
Example usage:

.. code-block:: python

   from edsl.questions import QuestionLikertFive

   q = QuestionLikertFive(
      question_name = "happy",
      question_text = "I am only happy when it rains."
   )

An example can also be created using the `example` method:

.. code-block:: python

   QuestionLikertFive.example()
    

.. automodule:: edsl.questions.derived.QuestionLikertFive
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: likert_options, question_type, main


QuestionRank class
^^^^^^^^^^^^^^^^^^
A subclass of the `Question` class for creating questions where the response is a ranked list of options.
It specially requires a `question_options` list of strings for the options.
The number of options that *must* be selected can be optionally specified when creating the question. 
If not specified, all options are included (ranked) in the response.
Example usage:

.. code-block:: python

   from edsl.questions import QuestionRank

   q = QuestionRank(
      question_name = "foods_rank",
      question_text = "Rank the following foods.",
      question_options = ["Pizza", "Pasta", "Salad", "Soup"],
      num_selections = 2 # optional
   )

An example can also be created using the `example` method:

.. code-block:: python

   QuestionRank.example()

Alternatively, `QuestionTopK` can be used to ask the respondent to select a specific number of options from a list.
(See the next section for details.)

.. automodule:: edsl.questions.QuestionRank
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: question_type, question_options, num_selections, main


QuestionTopK class
^^^^^^^^^^^^^^^^^^
A subclass of the `QuestionMultipleChoice` class for creating questions where the response is a list of ranked items.
It specially requires a `question_options` list of strings for the options and the number of options that must be selected (`num_selections`).
Example usage:

.. code-block:: python

    from edsl.questions import QuestionTopK

    q = QuestionTopK(
        question_name = "foods_rank", 
        question_text = "Select the best foods.", 
        question_options = ["Pizza", "Pasta", "Salad", "Soup"],
        min_selections = 2,
        max_selections = 2
    )

An example can also be created using the `example` method:

    .. code-block:: python

        QuestionTopK.example()


.. automodule:: edsl.questions.derived.QuestionTopK
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: question_type, main


QuestionYesNo class
^^^^^^^^^^^^^^^^^^^
A subclass of the `QuestionMultipleChoice` class for creating multiple choice questions where the answer options are already specified: ['Yes', 'No'].
Example usage:

.. code-block:: python

    from edsl.questions import QuestionYesNo

    q = QuestionYesNo(
        question_name = "student",
        question_text = "Are you a student?"
    )

An example can also be created using the `example` method:

.. code-block:: python

    QuestionYesNo.example()


.. automodule:: edsl.questions.derived.QuestionYesNo
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: question_type, question_options, main


QuestionList class
^^^^^^^^^^^^^^^^^^
A subclass of the `Question` class for creating questions where the response is a list of strings.
The maximum number of items in the list can be specified using the `max_list_items` parameter.
Example usage:

.. code-block:: python

    q = QuestionList(
        question_name = "activities",
        question_text = "What activities do you enjoy most?",
        max_list_items = 5 # optional
    )

An example can also be created using the `example` method:

    .. code-block:: python
    
        QuestionList.example()


.. automodule:: edsl.questions.QuestionList
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: allow_nonresponse, question_type, max_list_items, main


QuestionBudget class
^^^^^^^^^^^^^^^^^^^^
A subclass of the `Question` class for creating questions where the response is an allocation of a sum among a list of options in the form of a dictionary where the keys are the options and the values are the allocated amounts.
It specially requires a `question_options` list of strings for the options and a `budget_sum` number for the total sum to be allocated.
Example usage:

.. code-block:: python

   from edsl.questions import QuestionBudget

   q = QuestionBudget(
      question_name = "food_budget", 
      question_text = "How would you allocate $100?", 
      question_options = ["Pizza", "Ice cream", "Burgers", "Salad"], 
      budget_sum = 100
   )

An example can also be created using the `example` method:

.. code-block:: python
    
   QuestionBudget.example()


.. automodule:: edsl.questions.QuestionBudget
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: question_type, question_options, budget_sum, main


QuestionExtract class
^^^^^^^^^^^^^^^^^^^^^
A subclass of the `Question` class for creating questions where the response is information extracted (or extrapolated) from a given text and formatted according to a specified template.
Example usage:

.. code-block:: python

    from edsl.questions import QuestionExtract

    q = QuestionExtract(
        question_name = "course_schedule",
        question_text = """This semester we are offering courses on 
        calligraphy on Friday mornings.""",
        answer_template = {"course_topic": "AI", "days": ["Monday", 
        "Wednesday"]}
    )

An example can also be created using the `example` method:
    
    .. code-block:: python

        QuestionExtract.example()


.. automodule:: edsl.questions.QuestionExtract
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: question_type, answer_template, main



QuestionFunctional class
^^^^^^^^^^^^^^^^^^^^^^^^
A subclass of the `Question` class for creating questions where the response is generated by a function instead of a lanugage model.
The question type is not intended to be used directly in a survey, but rather to generate responses for other questions.
This can be useful where a model is not needed for part of a survey, for questions that require some kind of initial computation, or for questions that are the result of a multi-step process.
The question type lets us define a function `func` that takes in a scenario and (optional) agent traits and returns an answer.

Example usage:

Say we have some survey results where we asked some agents to pick a random number:

.. code-block:: python

   from edsl.questions import QuestionNumerical
   from edsl import Agent

   q_random = QuestionNumerical(
      question_name = "random",
      question_text = "Choose a random number between 1 and 1000."
   )

   agents = [Agent({"persona":p}) for p in ["Dog catcher", "Magician", "Spy"]]

   results = q_random.by(agents).run()
   results.select("persona", "random").print(format="rich")


The results are:

.. code-block:: text

   ┏━━━━━━━━━━━━━┳━━━━━━━━━┓
   ┃ agent       ┃ answer  ┃
   ┃ .persona    ┃ .random ┃
   ┡━━━━━━━━━━━━━╇━━━━━━━━━┩
   │ Dog catcher │ 472     │
   ├─────────────┼─────────┤
   │ Magician    │ 537     │
   ├─────────────┼─────────┤
   │ Spy         │ 528     │
   └─────────────┴─────────┘


We can use `QuestionFunctional` to evaluate the responses using a function instead of calling the language model to answer another question.
The responses are passed to the function as scenarios, and then the function is passed to the `QuestionFunctional` object:

.. code-block:: python

   from edsl.questions import QuestionFunctional

   def my_function(scenario, agent_traits):
      if scenario.get("persona") == "Magician":
         return "Magicians never pick randomly!"
      elif scenario.get("random") > 500:
         return "Top half"
      else:
         return "Bottom half"

   q_evaluate = QuestionFunctional(
      question_name = "evaluate",
      func = my_function
   )


Next we turn the responses into scenarios for the function:

.. code-block:: python

   scenarios = results.select("persona", "random").to_scenarios()
   scenarios

We can inspect the scenarios:

.. code-block:: python

   [Scenario({'persona': 'Dog catcher', 'random': 472}),
   Scenario({'persona': 'Magician', 'random': 537}),
   Scenario({'persona': 'Spy', 'random': 528})]


Finally, we run the function with the scenarios:

.. code-block:: python

   results = q_evaluate.by(scenarios).run()
   results.select("persona", "random", "evaluate").print(format="rich")


The results are:

.. code-block:: text

   ┏━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ scenario    ┃ scenario ┃ answer                         ┃
   ┃ .persona    ┃ .random  ┃ .evaluate                      ┃
   ┡━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ Dog catcher │ 472      │ Bottom half                    │
   ├─────────────┼──────────┼────────────────────────────────┤
   │ Magician    │ 537      │ Magicians never pick randomly! │
   ├─────────────┼──────────┼────────────────────────────────┤
   │ Spy         │ 528      │ Top half                       │
   └─────────────┴──────────┴────────────────────────────────┘


Another example of `QuestionFunctional` can be seen in the following notebook, where we give agents different instructions for generating random numbers and then use a function to identify whether the responses are identical.

Example notebook: `Simulating randomness <https://docs.expectedparrot.com/en/latest/notebooks/random_numbers.html>`_ 



.. automodule:: edsl.questions.QuestionFunctional
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: question_type, answer_template, main



Other classes & methods
-----------------------

.. automodule:: edsl.questions.settings
   :members:
   :undoc-members:
   :show-inheritance:

.. .. automodule:: edsl.questions.compose_questions
..    :members:
..    :undoc-members:
..    :show-inheritance:

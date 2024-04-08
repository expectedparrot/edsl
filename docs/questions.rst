.. _questions:

Questions
=========

.. This module contains the Question class, which is the base class for all questions in EDSL.

EDSL includes templates for many common question types, including multiple choice, checkbox, free text, numerical, linear scale, Likert scale and others.
Each question type inherits from the `Question` class and implements its own methods for validating answers and responses from language models.

Every question type requires a question name and question text. 
The `question_name` is a unique identifier for the question with no spaces or special characters (e.g., "favorite_primary_color" but not "favorite primary color").
The `question_text` is the text of the question itself written as a string (e.g., "What is your favorite primary color?").

Some question types require additional fields, such as a `question_options` list of strings for multiple choice questions or list of integers for linear scale questions.


Constructing a question
-----------------------
Select and import a question type based on the desired output. 
For example, to create a multiple choice question:

.. code-block:: python

   from edsl import QuestionMultipleChoice

Construct a question in the question type template:

.. code-block:: python

   q = QuestionMultipleChoice(
      question_name = "favorite_primary_color",
      question_text = "Which is your favorite primary color?",
      question_options = ["Red", "Yellow", "Blue"]
   )

You can also use the `example()` method to show an example of any question type:

.. code-block:: python

   QuestionMultipleChoice.example()


Simulating a response
---------------------
We can administer a single question to the default language model by calling the `run` method for the question object and store the results:

.. code-block:: python

   result = q.run()
    
If the question is part of a survey of one or more questions, the `run` method is called for the survey object instead:

.. code-block:: python
    
   q1 = ...
   q2 = ...

   from edsl import Survey

   survey = Survey(questions = [q1, q2])

   results = survey.run()

Learn more about constructing surveys in the :ref:`surveys` section.


Inspecting results 
------------------
The `run` method returns a `Results` object which is a list of individual `Result` objects for each response to the question or survey. 
Results can be printed, saved, analyzed and visualized in a variety of built-in methods.
See examples of results and details about these methods in the :ref:`results` section.


Specifying agents and models
----------------------------
In the examples above the results were simulated with the default language model (GPT 4), and no agent traits were specified.
Agent traits and language models can be specified by creating `Agent` and `Model` objects and assigning them to a survey (or single question) with the `by` method when running it.
For example, if we want to specify that our survey be answered by an AI agent that is a student we create an `Agent` object and pass it the desired traits:

.. code-block:: python

   from edsl import Agent

   agent = Agent(traits = {"persona": "You are a student."})

   results = survey.by(agent).run()

To specify a different language model for the survey, we can first check the available models:

.. code-block:: python

   from edsl import Model

   Model.available()

This will return a list of models to choose from:

.. code-block:: python

   ['gpt-3.5-turbo',
   'gpt-4-1106-preview',
   'gemini_pro',
   'llama-2-13b-chat-hf',
   'llama-2-70b-chat-hf',
   'mixtral-8x7B-instruct-v0.1']

We can create a `Model` object to use when running the survey:

.. code-block:: python

   model = Model('llama-2-70b-chat-hf') 

   results = survey.by(agent).by(model).run()

If multiple agents or models are desired, they can be added together as a list in the same `by` method:

.. code-block:: python

   results = survey.by([agent1, agent2]).by([model1, model2]).run()
   

Parameterizing a question
-------------------------
Questions can be parameterized to include variables that are replaced with specific values when the questions are run.
This allows us to create multiple versions of a question that can be administered at once in a survey, or according to some special logic.

Key steps:

* Create a question that takes a parameter in double braces:

.. code-block:: python

   from edsl.questions import QuestionFreeText

   q = QuestionFreeText(
      question_name = "favorite_item",
      question_text = "What is your favorite {{ item }}?",
   )

* Create a dictionary for the value that will replace the parameter and store it in a `Scenario` object:

.. code-block:: python

   scenario = Scenario({"item": "color"})

If multiple values will be used, create multiple `Scenario` objects in a list:

.. code-block:: python

   scenarios = [Scenario({"item": item}) for item in ["color", "food"]]

* Add the scenarios to the question with the `by` method when running it:

.. code-block:: python

   results = q.by(scenarios).run()

If the question is part of a survey, add the scenarios to the survey instead:

.. code-block:: python

   q1 = ...
   q2 = ...

   from edsl import Survey 

   survey = Survey([q1, q2])

   results = survey.by(scenarios).run()

As with agents and models, scenarios should be added together as a list in the same `by` method.

Learn more about specifying question scenarios, agents and language models in their respective sections:

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

QuestionMultipleChoice class
----------------------------
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
----------------------
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
----------------------
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
-------------------------
A subclass of the `QuestionMultipleChoice` class for creating linear scale questions.
It requires a `question_options` list of integers for the scale.
Example usage:

.. code-block:: python

   from edsl.questions import QuestionLinearScale

   q = QuestionLinearScale(
      question_name = "studying",
      question_text = """On a scale from 0 to 5, how much do you 
      enjoy studying? (0 = not at all, 5 = very much)""",
      question_options = [0, 1, 2, 3, 4, 5]
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
-------------------------
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
-------------------
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
-------------------
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
-------------------
A subclass of the `QuestionMultipleChoice` class for creating questions where the response is a list of ranked items.
It specially requires a `question_options` list of strings for the options and the number of options that must be selected (`num_selections`).
Example usage:

.. code-block:: python

    from edsl.questions import QuestionTopK

    q = QuestionTopK(
        question_name = "foods_rank", 
        question_text = "Select the best foods.", 
        question_options = ["Pizza", "Pasta", "Salad", "Soup"],
        num_selections = 2
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
-------------------
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
------------------
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
----------------------------
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
----------------------------
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


Other classes & methods
-----------------------

.. automodule:: edsl.questions.settings
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: edsl.questions.compose_questions
   :members:
   :undoc-members:
   :show-inheritance:

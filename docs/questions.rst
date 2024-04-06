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

.. automodule:: edsl.questions.QuestionMultipleChoice
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: purpose, question_type, question_options, main
   
QuestionCheckBox class
----------------------

.. automodule:: edsl.questions.QuestionCheckBox
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: purpose, question_type, question_options, min_selections, max_selections, main

QuestionFreeText class
----------------------

.. automodule:: edsl.questions.QuestionFreeText
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: allow_nonresponse, default_instructions, question_type, main

QuestionLinearScale class
-------------------------

.. automodule:: edsl.questions.derived.QuestionLinearScale
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: question_type, question_options, option_labels, main

QuestionNumerical class
-------------------------

.. automodule:: edsl.questions.QuestionNumerical
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: question_type, min_value, max_value, main

QuestionLikertFive class
-------------------

.. automodule:: edsl.questions.derived.QuestionLikertFive
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: likert_options, question_type, main

QuestionRank class
-------------------

.. automodule:: edsl.questions.QuestionRank
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: question_type, question_options, num_selections, main

QuestionTopK class
-------------------

.. automodule:: edsl.questions.derived.QuestionTopK
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: question_type, main

QuestionYesNo class
-------------------

.. automodule:: edsl.questions.derived.QuestionYesNo
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: question_type, question_options, main

QuestionList class
------------------

.. automodule:: edsl.questions.QuestionList
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: allow_nonresponse, question_type, max_list_items, main

QuestionBudget class
----------------------------

.. automodule:: edsl.questions.QuestionBudget
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: question_type, question_options, budget_sum, main

QuestionExtract class
----------------------------

.. automodule:: edsl.questions.QuestionExtract
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: question_type, answer_template, main

QuestionFunctional class
-------------------

.. automodule:: edsl.questions.QuestionFunctional
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: answer_question_directly, default_instructions, func, question_type

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

.. automodule:: edsl.questions.question_registry
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: edsl.questions.AnswerValidatorMixin
   :members:
   :undoc-members:
   :show-inheritance:

.. automodule:: edsl.questions.descriptors
   :members:
   :undoc-members:
   :show-inheritance:
.. _questions:

Questions
=========

.. This module contains the Question class, which is the base class for all questions in EDSL.

EDSL includes templates for many common question types: multiple choice, checkbox, free text, numerical, linear scale, list, rank, budget, extract, top k, Likert scale and yes/no.
Each question type inherits from the `Question` class and implements its own methods for validating answers and responses from language models.

Every question requires a question name and question text. 
A `question_name` is a unique identifier for the question, while `question_text` is the text of the question itself.

Some question types require additional fields, such as `question_options` for multiple choice questions.

Constructing a question
-----------------------
Select and import a question type based on the desired output. For example, to create a multiple choice question:

.. code-block:: python

   from edsl import QuestionMultipleChoice

Construct a question in the question type template. The `question_name` and `question_text` fields are required for all question types, and certain question types require additional fields. For example, a multiple choice question requires a `question_options` field:

.. code-block:: python

   q = QuestionMultipleChoice(
      question_name = "color",
      question_text = "What is your favorite color?",
      question_options = ["Red", "Blue", "Green", "Yellow"]
   )

You can also use the `example()` method to show an example of any question type:

.. code-block:: python

   QuestionMultipleChoice.example()


Simulating a response
---------------------
Administer the question to a language model by appending the `run` method to the question object:

.. code-block:: python

   results = q.run()
    
If the question is part of a survey, the method is appended to the survey object instead:

.. code-block:: python
    
   q1 = ...
   q2 = ...
   results = Survey([q1, q2]).run()

The `run` method returns a `Result` object for the question and the agent and model that simulated the response to it.
Results can be printed, saved, analyzed and visualized in a variety of built-in methods.
See details about these methods in the :ref:`results` module.

Learn more details about constructing surveys in the :ref:`surveys` module.

Specifying agents and models
----------------------------

In the example above the result was simulated with the default model (GPT 4) and agent (no persona).
Agent personas and language models can be specified by appending them to the question object before running it with the `by` method:

.. code-block:: python

   from edsl import Agent, Model

   a = Agent(traits = {"persona": "student"})
   m = Model('gpt-4-1106-preview') 

   results = q.by(a).by(m).run()

Parameterizing a question
-------------------------
Questions can be parameterized to include variables that are replaced with specific values when the question is run.
This allows you to create multiple versions of a question that can be administered at once in a survey.

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

* Add the `Scenario` objects to the question with the `by` method when running it:

.. code-block:: python

   results = q.by(scenarios).run()

If the question is part of a survey, add the `Scenario` objects to the survey:

.. code-block:: python

   q1 = ...
   q2 = ...

   from edsl import Survey 

   s = Survey([q1, q2])
   results = s.by(scenarios).run()

As with agents and models, scenarios should be added together as a list in the same `by` method.

Learn more about specifying question scenarios, agents and language models in their respective modules:

* :ref:`scenarios`
* :ref:`agents`
* :ref:`language_models`


QuestionBase class 
------------------

.. automodule:: edsl.questions.QuestionBase
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: question_name, question_text, question_type, short_names_dict, main

QuestionBudget class
----------------------------

.. automodule:: edsl.questions.QuestionBudget
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: question_type, question_options, budget_sum, main

QuestionCheckBox class
----------------------

.. automodule:: edsl.questions.QuestionCheckBox
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: purpose, question_type, question_options, min_selections, max_selections, main

QuestionExtract class
----------------------------

.. automodule:: edsl.questions.QuestionExtract
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: question_type, answer_template, main

QuestionFreeText class
----------------------

.. automodule:: edsl.questions.QuestionFreeText
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: allow_nonresponse, default_instructions, question_type, main

QuestionFunctional class
-------------------

.. automodule:: edsl.questions.QuestionFunctional
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: answer_question_directly, default_instructions, func, question_type

QuestionLikertFive class
-------------------

.. automodule:: edsl.questions.derived.QuestionLikertFive
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: likert_options, question_type, main

QuestionLinearScale class
-------------------------

.. automodule:: edsl.questions.derived.QuestionLinearScale
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: question_type, question_options, option_labels, main

QuestionList class
------------------

.. automodule:: edsl.questions.QuestionList
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: allow_nonresponse, question_type, max_list_items, main

QuestionMultipleChoice class
----------------------------

.. automodule:: edsl.questions.QuestionMultipleChoice
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: purpose, question_type, question_options, main
   
QuestionNumerical class
-------------------------

.. automodule:: edsl.questions.QuestionNumerical
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: question_type, min_value, max_value, main

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
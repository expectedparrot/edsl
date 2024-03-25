Questions
=========

.. This module contains the Question class, which is the base class for all questions in EDSL.

There are numerous types of questions: multiple choice, checkbox, free text, numerical, linear scale, list, rank, budget, extract, top k, Likert scale, yes/no.
Each question type inherits from the `Question` class and implements its own methods for validating answers and responses from the language model (LLM).

Every question requires a question name and question text. 
A question_name is a unique identifier for the question, while question_text is the text of the question itself.

Some question types require additional fields, such as question options for multiple choice questions.

Constructing a Question
-----------------------
Key steps:

* Import the `Question` class and select an appropriate question type. Available question types include multiple choice, checkbox, free text, numerical, linear scale, list, rank, budget, extract, top k, Likert scale, yes/no.

* Import the question type class. For example, to create a multiple choice question:

.. code-block:: python

   from edsl import QuestionMultipleChoice

* Construct a question in the required format. All question types require a question name and question text. Some question types require additional fields, such as question options for multiple choice questions:

.. code-block:: python

   q = QuestionMultipleChoice(
      question_name = "color",
      question_text = "What is your favorite color?",
      question_options = ["Red", "Blue", "Green", "Yellow"]
   )

To see an example of a question type in the required format, use the question type `example()` method:

.. code-block:: python

   QuestionMultipleChoice.example()


Simulating a response
---------------------
Administer the question to an agent with the `run` method. A single question can be run individually by appending the `run` method directly to the question object:

.. code-block:: python

   results = q.run()
    
If the question is part of a survey, the method is appended to the survey object instead:

.. code-block:: python
    
   q1 = ...
   q2 = ...
   results = Survey([q1, q2]).run()

(See more details about surveys in the :ref:`surveys` module.)


The `run` method administers a question to the LLM and returns the response in a `Results` object.
Results can be printed, saved, analyzed and visualized in a variety of built-in methods.
See details about these methods in the :ref:`results` module.

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

* Create a dictionary for the value that will replace the parameter and store it in a Scenario object:

.. code-block:: python

   scenario = Scenario({"item": "color"})

If multiple values will be used, create multiple Scenario objects in a list:

.. code-block:: python

   scenarios = [Scenario({"item": item}) for item in ["color", "food"]]

* Add the Scenario objects to the question with the `by` method before appending the `run` method:

.. code-block:: python

   results = q.by(scenarios).run()

If the question is part of a survey, add the Scenario objects to the survey:

.. code-block:: python

   q1 = ...
   q2 = ...
   results = Survey([q1, q2]).by(scenarios).run()

As with other Survey components (agents and language models), multiple Scenario objects should be added together as a list in the same `by` method.

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
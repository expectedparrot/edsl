Questions
=========

.. automodule:: edsl.questions.Question
   :noindex:

.. automethod:: Question.__init__
   :noindex:

.. automethod:: Question.add_question
   :noindex:

.. automethod:: Question.by
   :noindex:

.. automethod:: Question.from_dict
   :noindex:

.. automethod:: Question.rich_print
   :noindex:

.. automethod:: Question.run
   :noindex:

.. automethod:: Question.to_dict
   :noindex:

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
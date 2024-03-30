.. _surveys:

Surveys
=======

.. A Survey is collection of questions that can be administered to an Agent.

Constructing a Survey
---------------------
Key steps:

* Create questions
* Add questions to a survey
* Run the survey by sending it to an LLM

Before running the survey you can optionally:

* Add personas for AI agents that will respond to the survey
* Add rules and special logic (e.g., skip logic or memory of prior responses) (by default, questions are delivered asynchronously)
* Add values for parameterized questions (Scenario objects) 
* Specify the language models that will be used to answer the questions (the default model is GPT 4)

A survey can also be sent to Googe Forms, Survey Monkey, LimeSurvey and other survey 
platforms. 

Defining questions
^^^^^^^^^^^^^^^^^^
Questions can be defined as various types, including multiple choice, checkbox, free text, linear scale, numerical and other types.
The formats are defined in the `questions` module. Here we define some questions: 

.. code-block:: python

   from edsl.questions import QuestionMultipleChoice, 
   QuestionNumerical, QuestionFreeText

   q1 = QuestionMultipleChoice(
      question_name = "student",
      question_text = "Are you a student?",
      question_options = ["yes", "no"]
   )
   q2 = QuestionNumerical(
      question_name = "years",
      question_text = "How many years have you been in school?"
   )
   q3 = QuestionFreeText(
      question_name = "weekends",
      question_text = "What do you do on weekends?"
   )

Adding questions to a survey
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Questions are added to a Survey object as a list of question ids:

.. code-block:: python

   from edsl.surveys import Survey

   survey = Survey(questions=[q1, q2, q3])

Alternatively, questions can be added to a Survey one at a time:

.. code-block:: python

   survey = Survey().add_question(q1).add_question(q2)
    
Applying survey rules
^^^^^^^^^^^^^^^^^^^^^
Rules are applied to a Survey with the `add_rule` and `add_stop_rule` methods which take a logical expression and the relevant questions.
For example, the following rule specifies that if the response to q1 is "no" then the next question is q3 (a skip rule):

.. code-block:: python
    
   survey = survey.add_rule(q1, "student == 'no'", q3)

Here we apply a stop rule instead of a skip rule. If the response to q1 is "no", the survey will end after q1 is answered:

.. code-block:: python

   survey = survey.add_stop_rule(q1, "student == 'no'")

Writing conditional expressions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The expressions themselves ("student == 'no'") are written in Python.
An expression is evaluated to True or False, with the answer substituted into the expression. 
The placeholder for this answer is the name of the question itself. 
In the examples, the answer to q1 is substituted into the expression "student == 'no'", 
as the name of q1 is "student".

Memory
^^^^^^
When an agent is taking a survey, they can be prompted to "remember" answers to previous questions.
This can be done in several ways:

* Full memory: The agent is given all of the answers to the questions in the survey.

.. code-block:: python

   s.set_full_memory_mode()

Note that this is slow and token-intensive, as the questions must be answered serially and requires the agent to remember all of the answers to the questions in the survey.
In contrast, if the agent does not need to remember all of the answers to the questions in the survey, execution can proceed in parallel.
    
* Lagged memory: With each question, the agent is given the answers to the specified number of lagged (prior) questions.
In this example, the agent is given the answers to the 2 previous questions in the survey:

.. code-block:: python

   s.set_lagged_memory(2)

* Targeted memory: The agent is given the answers to specific targeted prior questions.
In this example, the agent is given the answer to q1 when prompted to to answer q2:

.. code-block:: python

   survey.add_targeted_memory(q2, q1)

We can also use question names instead of question ids. The following example is equivalent to the previous one:

.. code-block:: python

   survey.add_targeted_memory("years", "student")

This method can be applied multiple times to add prior answers to a given question.
For example, we can add answers to both q1 and q2 when answering q3:

.. code-block:: python

   survey.add_memory_collection(q3, q1)
   survey.add_memory_collection(q3, q2)

    
Running a survey
^^^^^^^^^^^^^^^^
Once constructed, a Survey can be `run`, creating a `Results` object:

.. code-block:: python

   results = survey.run()

If question scenarios, agents or language models have been specified, they are added to the survey with the `by` method when running it:

.. code-block:: python

   results = survey.by(scenarios).by(agents).by(models).run()

Note that these survey components can be chained in any order, so long as each type of component is chained at once (e.g., if adding multiple agents, use `by.(agents)` once where agents is a list of all Agent objects).

Learn more about specifying question scenarios, agents and language models in their respective modules:

* :ref:`scenarios`
* :ref:`agents`
* :ref:`language_models`

Survey class
------------

.. .. automodule:: edsl.surveys.base
   .. :members:
   .. :undoc-members:
   .. :show-inheritance:

.. .. automodule:: edsl.surveys.descriptors
..    :members:
..    :undoc-members:
..    :show-inheritance:

.. automodule:: edsl.surveys.Survey
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members:

SurveyExportMixin class
-----------------------

.. automodule:: edsl.surveys.SurveyExportMixin
   :members:
   :undoc-members:
   :show-inheritance:

Rule class
----------

.. automodule:: edsl.surveys.Rule
   :members:
   :undoc-members:
   :show-inheritance:

RuleCollection class
--------------------

.. automodule:: edsl.surveys.RuleCollection
   :members:
   :undoc-members:
   :show-inheritance:

Memory class
------------

.. automodule:: edsl.surveys.Memory
   :members:
   :undoc-members:
   :show-inheritance:

MemoryPlan class
----------------

.. automodule:: edsl.surveys.MemoryPlan
   :members:
   :undoc-members:
   :show-inheritance:

DAG class
---------

.. automodule:: edsl.surveys.DAG
   :members:
   :undoc-members:
   :show-inheritance:


.. _surveys:

Surveys
=======

A `Survey` is collection of questions that can be administered asynchronously to one or more agents and language models, or according to specified rules such as skip or stop logic.

The key steps to creating and conducting a survey are:

* Creating `Question` objects of any type (multiple choice, free text, linear scale, etc.)
* Passing questions to a `Survey` 
* Running the survey by sending it to a language `Model` 

Before running the survey you can optionally:

* Add traits for an AI `Agent` (or `AgentList`) that will respond to the survey 
* Add conditional rules or "memory" of responses to other questions
* Add values for parameterized questions (`Scenario` objects) 

*Coming soon:*
An EDSL survey can also be exported to other platforms such as LimeSurvey, Google Forms, Qualtrics and SurveyMonkey. 
This can be useful for combining responses from AI and human audiences. 
See a `demo notebook <https://docs.expectedparrot.com/en/latest/notebooks/export_survey_updates.html>`_.



Constructing a survey
---------------------

Defining questions
^^^^^^^^^^^^^^^^^^
Questions can be defined as various types, including multiple choice, checkbox, free text, linear scale, numerical and other types.
The formats are defined in the `questions` module. Here we define some questions: 

.. code-block:: python

   from edsl.questions import QuestionYesNo, QuestionNumerical, QuestionFreeText

   q1 = QuestionYesNo(
      question_name = "high_school_student",
      question_text = "Are you a high school student?"
   )
   q2 = QuestionNumerical(
      question_name = "age",
      question_text = "How old are you?"
   )
   q3 = QuestionFreeText(
      question_name = "favorite_class",
      question_text = "What is your favorite class?"
   )
   q4 = QuestionFreeText(
      question_name = "favorite_sport",
      question_text = "What is your favorite sport?"
   )

Adding questions to a survey
^^^^^^^^^^^^^^^^^^^^^^^^^^^^
Questions are passed to a `Survey` object as a list of question ids:

.. code-block:: python

   from edsl.surveys import Survey

   survey = Survey(questions = [q1, q2, q3, q4])

Alternatively, questions can be added to a survey one at a time:

.. code-block:: python

   survey = Survey().add_question(q1).add_question(q2).add_question(q3).add_question(q4)
    

Applying survey rules
^^^^^^^^^^^^^^^^^^^^^
Rules can be applied to a survey with the `add_skip_rule()`, `add_stop_rule()` and `add_rule()` methods, which take a logical expression and the relevant questions.

**Skip rules:**
The `add_skip_rule()` method skips a question if a condition is met. 
The (2) required parameters are the question to skip and the condition to evaluate.

Here we use `add_skip_rule()` to skip q2 if the response to "high_school_student" is "No".
Note that we can refer to the question to be skipped using either the question name or the question id:

.. code-block:: python

   survey = Survey(questions = [q1, q2, q3, q4])
   survey = survey.add_skip_rule(q2, "high_school_student == 'No'")


This is equivalent:

.. code-block:: python

   survey = Survey(questions = [q1, q2, q3, q4])
   survey = survey.add_skip_rule("age", "high_school_student == 'No'")


We can run the survey and verify that the rule was applied:

.. code-block:: python
    
   results = survey.run()
   results.select("high_school_student", "age", "favorite_class", "favorite_sport").print(format="rich")


This will print the answers, showing that q2 was skipped:

.. code-block:: text
    
   ┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ answer               ┃ answer ┃ answer                                 ┃ answer                                 ┃
   ┃ .high_school_student ┃ .age   ┃ .favorite_class                        ┃ .favorite_sport                        ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ No                   │ None   │ My favorite class is literature        │ My favorite sport is basketball. I     │
   │                      │        │ because it allows me to explore        │ love the fast-paced action and the     │
   │                      │        │ diverse perspectives and immerse       │ skill involved in shooting and         │
   │                      │        │ myself in different cultures through   │ teamwork.                              │
   │                      │        │ the power of storytelling.             │                                        │
   └──────────────────────┴────────┴────────────────────────────────────────┴────────────────────────────────────────┘

(To learn about accessing and analyzing all components of the `Results` object, not just the answers, see the :ref:`results` module.)


**Stop rules:**
The `add_stop_rule()` method stops the survey if a condition is met.
The (2) required parameters are the question to stop at and the condition to evaluate.

Here we use `add_stop_rule()` to end the survey if the response to "high_school_student" is "No":

.. code-block:: python

   survey = Survey(questions = [q1, q2, q3, q4])
   survey = survey.add_stop_rule(q1, "high_school_student == 'No'")


This time we see that the survey ended when the response to "high_school_student" was "No":

.. code-block:: python
    
   results = survey.run()
   results.select("high_school_student", "age", "favorite_class", "favorite_sport").print(format="rich")

.. code-block:: python
    
   ┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
   ┃ answer               ┃ answer ┃ answer          ┃ answer          ┃
   ┃ .high_school_student ┃ .age   ┃ .favorite_class ┃ .favorite_sport ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
   │ No                   │ None   │ None            │ None            │
   └──────────────────────┴────────┴─────────────────┴─────────────────┘


**Rules:**
The `add_rule()` method specifies that if a condition is met, a specific question should be administered next.
The (3) required parameters are the question to evaluate, the condition to evaluate, and the question to administer next.

Here we use `add_rule()` to specify that if the response to "high_school_student" is "No" then q4 should be administered next:

.. code-block:: python
   
   survey = Survey(questions = [q1, q2, q3, q4])
   survey = survey.add_rule(q1, "high_school_student == 'No'", q4)


We can run the survey and verify that the rule was applied:

.. code-block:: python
    
   results = survey.run()
   results.select("high_school_student", "age", "favorite_class", "favorite_sport").print(format="rich")


We can see that q2 and q3 were skipped because the response to "high_school_student" was "No":

.. code-block:: text
    
   ┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ answer               ┃ answer ┃ answer          ┃ answer                                                        ┃
   ┃ .high_school_student ┃ .age   ┃ .favorite_class ┃ .favorite_sport                                               ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ No                   │ None   │ None            │ My favorite sport is basketball. I love the fast-paced action │
   │                      │        │                 │ and the skill involved in shooting and teamwork.              │
   └──────────────────────┴────────┴─────────────────┴───────────────────────────────────────────────────────────────┘


Conditional expressions
^^^^^^^^^^^^^^^^^^^^^^^
The expressions themselves (`"student == 'No'"`) are written in Python.
An expression is evaluated to True or False, with the answer substituted into the expression. 
The placeholder for this answer is the name of the question itself. 
In the examples, the answer to q1 is substituted into the expression `"student == 'No'"`, 
as the name of q1 is "student".


Memory
^^^^^^
When an agent is taking a survey, they can be prompted to "remember" answers to previous questions.
This can be done in several ways:

**Full memory:**
The agent is given all of the answers to the questions in the survey.

.. code-block:: python

   survey = Survey(questions = [q1, q2, q3, q4])
   survey.set_full_memory_mode()

Note that this is slow and token-intensive, as the questions must be answered serially and requires the agent to remember all of the answers to the questions in the survey.
In contrast, if the agent does not need to remember all of the answers to the questions in the survey, execution can proceed in parallel.
    
**Lagged memory:**
With each question, the agent is given the answers to the specified number of lagged (prior) questions.
In this example, the agent is given the answers to the 2 previous questions in the survey:

.. code-block:: python

   survey = Survey(questions = [q1, q2, q3, q4])
   survey.set_lagged_memory(2)

**Targeted memory:**
The agent is given the answers to specific targeted prior questions.
In this example, the agent is given the answer to q1 when prompted to to answer q2:

.. code-block:: python

   survey = Survey(questions = [q1, q2, q3, q4])
   survey.add_targeted_memory(q4, q1)

We can also use question names instead of question ids. The following example is equivalent to the previous one:

.. code-block:: python

   survey = Survey(questions = [q1, q2, q3, q4])
   survey.add_targeted_memory("favorite_sport", "high_school_student")

This method can be applied multiple times to add prior answers to a given question.
For example, we can add answers to both q1 and q2 when answering q3:

.. code-block:: python

   survey = Survey(questions = [q1, q2, q3, q4])
   survey.add_memory_collection(q4, q1)
   survey.add_memory_collection(q4, q2)

    
Running a survey
----------------
Once constructed, a Survey can be `run`, creating a `Results` object:

.. code-block:: python

   results = survey.run()

If question scenarios, agents or language models have been specified, they are added to the survey with the `by` method when running it:

.. code-block:: python

   results = survey.by(scenarios).by(agents).by(models).run()

Note that these survey components can be chained in any order, so long as each type of component is chained at once (e.g., if adding multiple agents, use `by.(agents)` once where agents is a list of all Agent objects).


Exporting a survey to other platforms
-------------------------------------
*Coming soon!*
An EDSL survey can also be exported to other survey platforms, such as LimeSurvey, Google Forms, Qualtrics and SurveyMonkey.
This is useful for combining responses from AI and human audiences. 
We do this by calling the `web` method and specifying the destination platform.

For example, to export a survey to LimeSurvey:

.. code-block:: python

   ls_survey = survey.web(platform="lime_survey")

To get the url of the newly created survey:

.. code-block:: python

   ls_survey.json()["data"]["url"]

This will return a url that can be used to access the survey on LimeSurvey.

Or to export to Google Forms:

.. code-block:: python

   survey.web(platform="google_forms")

*Note:* This feature is in launching soon! This page will be updated when it is live. 
If you would like to sign up for alpha testing this and other new features, please complete the following survey which was created with this new method: [EDSL signup survey ](https://survey.expectedparrot.com/index.php/132345).</i>


Learn more about specifying question scenarios, agents and language models in their respective modules:

* :ref:`scenarios`
* :ref:`agents`
* :ref:`language_models`

Survey class
------------

.. automodule:: edsl.surveys.Survey
   :members: 
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members:

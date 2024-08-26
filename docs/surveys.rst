.. _surveys:

Surveys
=======

A `Survey` is collection of questions that can be administered asynchronously to one or more agents and language models, or according to specified rules such as skip or stop logic.

The key steps to creating and conducting a survey are:

* Creating `Question` objects of any type (multiple choice, checkbox, free text, numerical, linear scale, etc.)
* Passing questions to a `Survey`
* Running the survey by sending it to a language `Model`

When running a survey you can optionally:

* Add traits for an AI `Agent` (or an `AgentList` of multiple agents) to respond to the survey 
* Add values for parameterized questions (`Scenario` objects) 
* Add conditional rules/logic, context and "memory" of responses to other questions

Running a survey automatically generates a `Results` object containing the responses and other components of the survey (questions, agents, scenarios, models, prompts, etc.). 
See the :ref:`results` module for more information on working with `Results` objects.


Key methods 
-----------
A survey is administered by calling the `run()` method on the `Survey` object, after adding any agents, scenarios and models with the `by()` method, and any survey rules or memory with the appropriate methods.
The methods for adding survey rules and memory include the following, which are each discussed in more detail below:

* `add_skip_rule()` - Skip a question based on a conditional expression (e.g., the response to another question).
* `add_stop_rule()` - End the survey based on a conditional expression.
* `add_rule()` - Administer a specified question next based on a conditional expression.
* `set_full_memory_mode()` - Include a memory of all prior questions/answers at each new question in the survey.
* `set_lagged_memory()` - Include a memory of a specified number of prior questions/answers at each new question in the survey.
* `add_targeted_memory()` - Include a memory of a specific question/answer at another question in the survey.
* `add_memory_collection()` - Include memories of a set of prior questions/answers at any other question in the survey.

Piping
^^^^^^
You can also pipe components of other questions into a question, for example, to reference the response to a previous question in a later question.

Flow
^^^^
A special method `show_flow()` will display the flow of the survey, showing the order of questions and any rules that have been applied.


*Request access:*
An EDSL survey can also be exported to other platforms such as LimeSurvey, Google Forms, Qualtrics and SurveyMonkey. 
This can be useful for combining responses from AI and human audiences. 
See a `demo notebook <https://docs.expectedparrot.com/en/latest/notebooks/export_survey_updates.html>`_.



Constructing a survey
---------------------

Defining questions
^^^^^^^^^^^^^^^^^^
Questions can be defined as various types, including multiple choice, checkbox, free text, linear scale, numerical and other types.
The formats are defined in the `questions` module. 
Here we define some questions that we use to create a `Survey` object and demonstrate methods for applying survey rules and memory: 

.. code-block:: python

   from edsl.questions import QuestionMultipleChoice, QuestionLinearScale, QuestionTopK
   from edsl import Survey

   q1 = QuestionMultipleChoice(
      question_name = "color",
      question_text = "What is your favorite color?",
      question_options = ["Red", "Orange", "Yellow", "Green", "Blue", "Purple"]
   )
   q2 = QuestionMultipleChoice(
      question_name = "day",
      question_text = "What is your favorite day of the week?",
      question_options = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
   )
   q3 = QuestionLinearScale(
      question_name = "winter",
      question_text = "How much do you enjoy winter?",
      question_options = [0,1,2,3,4,5],
      option_labels = {0: "Hate it", 5: "Love it"}
   )
   q4 = QuestionTopK(
      question_name = "birds",
      question_text = "Which birds do you like best?",
      question_options = ["Parrot", "Osprey", "Falcon", "Eagle", "First Robin of Spring"],
      min_selections = 2,
      max_selections = 2
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
    

Survey rules & logic
--------------------
Rules can be applied to a survey with the `add_skip_rule()`, `add_stop_rule()` and `add_rule()` methods, which take a logical expression and the relevant questions.


Skip rules
^^^^^^^^^^
The `add_skip_rule()` method skips a question if a condition is met. 
The (2) required parameters are the question to skip and the condition to evaluate.

Here we use `add_skip_rule()` to skip q2 if the response to "color" is "Blue".
Note that we can refer to the question to be skipped using either the id ("q2") or question_name ("day"):

.. code-block:: python

   survey = Survey(questions = [q1, q2, q3, q4])
   survey = survey.add_skip_rule(q2, "color == 'Blue'")


This is equivalent:

.. code-block:: python

   survey = Survey(questions = [q1, q2, q3, q4])
   survey = survey.add_skip_rule("day", "color == 'Blue'")


We can run the survey and verify that the rule was applied:

.. code-block:: python
    
   results = survey.run()
   results.select("color", "day", "winter", "birds").print(format="rich")


This will print the answers, showing that q2 was skipped (the response is "None"):

.. code-block:: text
    
   ┏━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
   ┃ answer ┃ answer ┃ answer  ┃ answer              ┃
   ┃ .color ┃ .day   ┃ .winter ┃ .birds              ┃
   ┡━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
   │ Blue   │ None   │ 3       │ ['Falcon', 'Eagle'] │
   └────────┴────────┴─────────┴─────────────────────┘


We can call the `show_flow()` method to display a graphic of the flow of the survey and see that q2 was skipped:

.. code-block:: python

   survey.show_flow()


.. image:: static/survey_show_flow.png
   :alt: Survey Flow Diagram
   :align: left

   <br>
   

Stop rules
^^^^^^^^^^
The `add_stop_rule()` method stops the survey if a condition is met.
The (2) required parameters are the question to stop at and the condition to evaluate.

Here we use `add_stop_rule()` to end the survey at q1 if the response is Blue:

.. code-block:: python

   survey = Survey(questions = [q1, q2, q3, q4])
   survey = survey.add_stop_rule(q1, "color == 'Blue'")


This time we see that the survey ended when the response to "color" was "Blue":

.. code-block:: python
    
   results = survey.run()
   results.select("color", "day", "winter", "birds").print(format="rich")

.. code-block:: text
    
   ┏━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┓
   ┃ answer ┃ answer ┃ answer  ┃ answer ┃
   ┃ .color ┃ .day   ┃ .winter ┃ .birds ┃
   ┡━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━┩
   │ Blue   │ None   │ None    │ None   │
   └────────┴────────┴─────────┴────────┘


Other rules
^^^^^^^^^^^
The generalizable `add_rule()` method is used to specify the next question to administer based on a condition.
The (3) required parameters are the question to evaluate, the condition to evaluate, and the question to administer next.

Here we use `add_rule()` to specify that if the response to "color" is "Blue" then q4 should be administered next:

.. code-block:: python
   
   survey = Survey(questions = [q1, q2, q3, q4])
   survey = survey.add_rule(q1, "color == 'Blue'", q4)


We can run the survey and verify that the rule was applied:

.. code-block:: python
    
   results = survey.run()
   results.select("color", "day", "winter", "birds").print(format="rich")


We can see that both q2 and q3 were skipped because the response to "color" was "Blue":

.. code-block:: text
    
   ┏━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━┓
   ┃ answer ┃ answer ┃ answer  ┃ answer              ┃
   ┃ .color ┃ .day   ┃ .winter ┃ .birds              ┃
   ┡━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━┩
   │ Blue   │ None   │ None    │ ['Falcon', 'Eagle'] │
   └────────┴────────┴─────────┴─────────────────────┘



Conditional expressions
^^^^^^^^^^^^^^^^^^^^^^^
The rule expressions themselves (`"student == 'No'"`) are written in Python.
An expression is evaluated to True or False, with the answer substituted into the expression. 
The placeholder for this answer is the name of the question itself. 
In the examples, the answer to q1 is substituted into the expression `"color == 'Blue'"`, 
as the name of q1 is "color".


Piping 
------
Piping is a method of explicitly referencing components of a question in a later question.
For example, here we use the answer to q0 in the prompt for q1:

.. code-block:: python

   from edsl import QuestionFreeText, QuestionList, Survey

   q0 = QuestionFreeText(
      question_name = "color",
      question_text = "What is your favorite color?", 
   )

   q1 = QuestionList(
      question_name = "examples",
      question_text = "Name some things that are {{ color.answer }}.", 
   )

   survey = Survey([q0, q1])

   results = survey.run()

   results.select("color", "examples").print(format="rich")

In this example, q0 will be administered before q1 and the response to q0 is piped into q1.
Output:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ answer                                                 ┃ answer                                                 ┃
   ┃ .color                                                 ┃ .examples                                              ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ Blue is my favorite color. It's calming and reminds me │ ['sky', 'ocean', 'blueberries', 'sapphires', 'blue     │
   │ of the sky and the ocean.                              │ jay', 'blue whale', 'blue jeans', 'cornflower',        │
   │                                                        │ 'forget-me-nots', 'bluebells']                         │
   └────────────────────────────────────────────────────────┴────────────────────────────────────────────────────────┘


If an answer is a list, we can index the items to use them as inputs.
Here we use an answer in question options:

.. code-block:: python

   from edsl import QuestionList, QuestionFreeText, QuestionMultipleChoice, Survey

   q0 = QuestionList(
      question_name = "colors",
      question_text = "What are your 3 favorite colors?", 
      max_list_items = 3
   )

   q1 = QuestionFreeText(
      question_name = "examples",
      question_text = "Name some things that are {{ colors.answer }}", 
   )

   q2 = QuestionMultipleChoice(
      question_name = "favorite",
      question_text = "Which is your #1 favorite color?", 
      question_options = [
         "{{ colors.answer[0] }}",
         "{{ colors.answer[1] }}",
         "{{ colors.answer[2] }}",
      ]
   )

   survey = Survey([q0, q1, q2])

   results = survey.run()

   results.select("colors", "examples", "favorite").print(format="rich")

Output:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┓
   ┃ answer                   ┃ answer                                                                   ┃ answer    ┃
   ┃ .colors                  ┃ .examples                                                                ┃ .favorite ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━┩
   │ ['Blue', 'Green', 'Red'] │ Some things that are blue include the sky, blueberries, and sapphires.   │ Blue      │
   │                          │ Things that are green are leaves, grass, and emeralds. Red items include │           │
   │                          │ roses, apples, and rubies.                                               │           │
   └──────────────────────────┴──────────────────────────────────────────────────────────────────────────┴───────────┘


This can also be done with agent traits. For example:

.. code-block:: python

   from edsl import Agent, QuestionFreeText

   a = Agent(traits = {'first_name': 'John'})

   q = QuestionFreeText(
      question_text = 'What is your last name, {{ agent.first_name }}?', 
      question_name = "example"
   )

   jobs = q.by(a)
   print(jobs.prompts().select('user_prompt').first().text)


This code will output the text of the prompt for the question:

.. code-block:: text

   You are being asked the following question: What is your last name, John?
   Return a valid JSON formatted like this:
   {"answer": "<put free text answer here>"}



Question memory
---------------
When an agent is taking a survey, they can be prompted to "remember" answers to previous questions.
This can be done in several ways:


Full memory
^^^^^^^^^^^
The method `set_full_memory_mode()` gives the agent all of the prior questions and answers at each new question in the survey,
i.e., the first question and answer are included in the memory when answering the second question, both the first and second questions and answers are included in the memory when answering the third question, and so on.
The method is called on the survey object:

.. code-block:: python

   survey = Survey(questions = [q1, q2, q3, q4])
   survey = survey.set_full_memory_mode()


In the results, we can inspect the `_user_prompt` for each question to see that the agent was prompted to remember all of the prior questions:

.. code-block:: python

   results = survey.run()
   results.select("color_user_prompt", "day_user_prompt", "winter_user_prompt", "birds_user_prompt").print(format="rich")


This will print the prompt that was used for each question, and we can see that each successive prompt references all prior questions and answers that were given:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ prompt                     ┃ prompt                    ┃ prompt                     ┃ prompt                    ┃
   ┃ .color_user_prompt         ┃ .day_user_prompt          ┃ .winter_user_prompt        ┃ .birds_user_prompt        ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ {'text': 'You are being    │ {'text': 'You are being   │ {'text': 'You are being    │ {'text': 'You are being   │
   │ asked the following        │ asked the following       │ asked the following        │ asked the following       │
   │ question: What is your     │ question: What is your    │ question: How much do you  │ question: Which birds do  │
   │ favorite color?\nThe       │ favorite day of the       │ enjoy winter?\nThe options │ you like best?\nThe       │
   │ options are\n\n0:          │ week?\nThe options        │ are\n\n0: 0\n\n1: 1\n\n2:  │ options are\n\n0:         │
   │ Red\n\n1: Orange\n\n2:     │ are\n\n0: Sun\n\n1:       │ 2\n\n3: 3\n\n4: 4\n\n5:    │ Parrot\n\n1: Osprey\n\n2: │
   │ Yellow\n\n3: Green\n\n4:   │ Mon\n\n2: Tue\n\n3:       │ 5\n\nReturn a valid JSON   │ Falcon\n\n3: Eagle\n\n4:  │
   │ Blue\n\n5:                 │ Wed\n\n4: Thu\n\n5:       │ formatted like this,       │ First Robin of            │
   │ Purple\n\nReturn a valid   │ Fri\n\n6: Sat\n\nReturn a │ selecting only the code of │ Spring\n\nReturn a valid  │
   │ JSON formatted like this,  │ valid JSON formatted like │ the option (codes start at │ JSON formatted like this, │
   │ selecting only the number  │ this, selecting only the  │ 0):\n{"answer": <put       │ selecting only the number │
   │ of the option:\n{"answer": │ number of the             │ answer code here>,         │ of the                    │
   │ <put answer code here>,    │ option:\n{"answer": <put  │ "comment": "<put           │ option:\n{"answer": [<put │
   │ "comment": "<put           │ answer code here>,        │ explanation here>"}\nOnly  │ comma-separated list of   │
   │ explanation here>"}\nOnly  │ "comment": "<put          │ 1 option may be            │ answer codes here>],      │
   │ 1 option may be            │ explanation here>"}\nOnly │ selected.\n        Before  │ "comment": "<put          │
   │ selected.', 'class_name':  │ 1 option may be           │ the question you are now   │ explanation               │
   │ 'MultipleChoice'}          │ selected.\n        Before │ answering, you already     │ here>"}\n\nYou must       │
   │                            │ the question you are now  │ answered the following     │ select exactly 2          │
   │                            │ answering, you already    │ question(s):\n             │ options.\n        Before  │
   │                            │ answered the following    │ \tQuestion: What is your   │ the question you are now  │
   │                            │ question(s):\n            │ favorite color?\n\tAnswer: │ answering, you already    │
   │                            │ \tQuestion: What is your  │ Blue\n\n Prior questions   │ answered the following    │
   │                            │ favorite                  │ and answers:\tQuestion:    │ question(s):\n            │
   │                            │ color?\n\tAnswer: Blue',  │ What is your favorite day  │ \tQuestion: What is your  │
   │                            │ 'class_name':             │ of the week?\n\tAnswer:    │ favorite                  │
   │                            │ 'MultipleChoice'}         │ Fri', 'class_name':        │ color?\n\tAnswer:         │
   │                            │                           │ 'LinearScale'}             │ Blue\n\n Prior questions  │
   │                            │                           │                            │ and answers:\tQuestion:   │
   │                            │                           │                            │ What is your favorite day │
   │                            │                           │                            │ of the week?\n\tAnswer:   │
   │                            │                           │                            │ Fri\n\n Prior questions   │
   │                            │                           │                            │ and answers:\tQuestion:   │
   │                            │                           │                            │ How much do you enjoy     │
   │                            │                           │                            │ winter?\n\tAnswer: 3',    │
   │                            │                           │                            │ 'class_name': 'TopK'}     │
   └────────────────────────────┴───────────────────────────┴────────────────────────────┴───────────────────────────┘


Note that this is slow and token-intensive, as the questions must be answered serially and requires the agent to remember all of the answers to the questions in the survey.
In contrast, if the agent does not need to remember all of the answers to the questions in the survey, execution can proceed in parallel.
    

Lagged memory
^^^^^^^^^^^^^
The method `set_lagged_memory()` gives the agent a specified number of prior questions and answers at each new question in the survey;
we pass it the number of prior questions and answers to remember.
Here we use it to give the agent just 1 prior question/answer at each question:

.. code-block:: python

   survey = Survey(questions = [q1, q2, q3, q4])
   survey = survey.set_lagged_memory(1)


We can inspect each `_user_prompt` again and see that the agent is only prompted to remember the last prior question/answer:

.. code-block:: python

   results = survey.run()
   results.select("color_user_prompt", "day_user_prompt", "winter_user_prompt", "birds_user_prompt").print(format="rich")


This will print the prompts for each question:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ prompt                     ┃ prompt                    ┃ prompt                     ┃ prompt                    ┃
   ┃ .color_user_prompt         ┃ .day_user_prompt          ┃ .winter_user_prompt        ┃ .birds_user_prompt        ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ {'text': 'You are being    │ {'text': 'You are being   │ {'text': 'You are being    │ {'text': 'You are being   │
   │ asked the following        │ asked the following       │ asked the following        │ asked the following       │
   │ question: What is your     │ question: What is your    │ question: How much do you  │ question: Which birds do  │
   │ favorite color?\nThe       │ favorite day of the       │ enjoy winter?\nThe options │ you like best?\nThe       │
   │ options are\n\n0:          │ week?\nThe options        │ are\n\n0: 0\n\n1: 1\n\n2:  │ options are\n\n0:         │
   │ Red\n\n1: Orange\n\n2:     │ are\n\n0: Sun\n\n1:       │ 2\n\n3: 3\n\n4: 4\n\n5:    │ Parrot\n\n1: Osprey\n\n2: │
   │ Yellow\n\n3: Green\n\n4:   │ Mon\n\n2: Tue\n\n3:       │ 5\n\nReturn a valid JSON   │ Falcon\n\n3: Eagle\n\n4:  │
   │ Blue\n\n5:                 │ Wed\n\n4: Thu\n\n5:       │ formatted like this,       │ First Robin of            │
   │ Purple\n\nReturn a valid   │ Fri\n\n6: Sat\n\nReturn a │ selecting only the code of │ Spring\n\nReturn a valid  │
   │ JSON formatted like this,  │ valid JSON formatted like │ the option (codes start at │ JSON formatted like this, │
   │ selecting only the number  │ this, selecting only the  │ 0):\n{"answer": <put       │ selecting only the number │
   │ of the option:\n{"answer": │ number of the             │ answer code here>,         │ of the                    │
   │ <put answer code here>,    │ option:\n{"answer": <put  │ "comment": "<put           │ option:\n{"answer": [<put │
   │ "comment": "<put           │ answer code here>,        │ explanation here>"}\nOnly  │ comma-separated list of   │
   │ explanation here>"}\nOnly  │ "comment": "<put          │ 1 option may be            │ answer codes here>],      │
   │ 1 option may be            │ explanation here>"}\nOnly │ selected.\n        Before  │ "comment": "<put          │
   │ selected.', 'class_name':  │ 1 option may be           │ the question you are now   │ explanation               │
   │ 'MultipleChoice'}          │ selected.\n        Before │ answering, you already     │ here>"}\n\nYou must       │
   │                            │ the question you are now  │ answered the following     │ select exactly 2          │
   │                            │ answering, you already    │ question(s):\n             │ options.\n        Before  │
   │                            │ answered the following    │ \tQuestion: What is your   │ the question you are now  │
   │                            │ question(s):\n            │ favorite day of the        │ answering, you already    │
   │                            │ \tQuestion: What is your  │ week?\n\tAnswer: Fri',     │ answered the following    │
   │                            │ favorite                  │ 'class_name':              │ question(s):\n            │
   │                            │ color?\n\tAnswer: Blue',  │ 'LinearScale'}             │ \tQuestion: How much do   │
   │                            │ 'class_name':             │                            │ you enjoy                 │
   │                            │ 'MultipleChoice'}         │                            │ winter?\n\tAnswer: 0',    │
   │                            │                           │                            │ 'class_name': 'TopK'}     │
   └────────────────────────────┴───────────────────────────┴────────────────────────────┴───────────────────────────┘


Targeted memory 
^^^^^^^^^^^^^^^
The method `add_targeted_memory()` gives the agent a targeted prior question and answer when answering another specified question.
We pass it the question to answer and the prior question/answer to remember when answering it.
Here we use it to give the agent the question/answer to q1 when prompting it to answer q4:

.. code-block:: python

   survey = Survey(questions = [q1, q2, q3, q4])
   survey = survey.add_targeted_memory(q4, q1)

   results = survey.run()
   results.select("color_user_prompt", "day_user_prompt", "winter_user_prompt", "birds_user_prompt").print(format="rich")


.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ prompt                     ┃ prompt                    ┃ prompt                     ┃ prompt                    ┃
   ┃ .color_user_prompt         ┃ .day_user_prompt          ┃ .winter_user_prompt        ┃ .birds_user_prompt        ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ {'text': 'You are being    │ {'text': 'You are being   │ {'text': 'You are being    │ {'text': 'You are being   │
   │ asked the following        │ asked the following       │ asked the following        │ asked the following       │
   │ question: What is your     │ question: What is your    │ question: How much do you  │ question: Which birds do  │
   │ favorite color?\nThe       │ favorite day of the       │ enjoy winter?\nThe options │ you like best?\nThe       │
   │ options are\n\n0:          │ week?\nThe options        │ are\n\n0: 0\n\n1: 1\n\n2:  │ options are\n\n0:         │
   │ Red\n\n1: Orange\n\n2:     │ are\n\n0: Sun\n\n1:       │ 2\n\n3: 3\n\n4: 4\n\n5:    │ Parrot\n\n1: Osprey\n\n2: │
   │ Yellow\n\n3: Green\n\n4:   │ Mon\n\n2: Tue\n\n3:       │ 5\n\nReturn a valid JSON   │ Falcon\n\n3: Eagle\n\n4:  │
   │ Blue\n\n5:                 │ Wed\n\n4: Thu\n\n5:       │ formatted like this,       │ First Robin of            │
   │ Purple\n\nReturn a valid   │ Fri\n\n6: Sat\n\nReturn a │ selecting only the code of │ Spring\n\nReturn a valid  │
   │ JSON formatted like this,  │ valid JSON formatted like │ the option (codes start at │ JSON formatted like this, │
   │ selecting only the number  │ this, selecting only the  │ 0):\n{"answer": <put       │ selecting only the number │
   │ of the option:\n{"answer": │ number of the             │ answer code here>,         │ of the                    │
   │ <put answer code here>,    │ option:\n{"answer": <put  │ "comment": "<put           │ option:\n{"answer": [<put │
   │ "comment": "<put           │ answer code here>,        │ explanation here>"}\nOnly  │ comma-separated list of   │
   │ explanation here>"}\nOnly  │ "comment": "<put          │ 1 option may be            │ answer codes here>],      │
   │ 1 option may be            │ explanation here>"}\nOnly │ selected.', 'class_name':  │ "comment": "<put          │
   │ selected.', 'class_name':  │ 1 option may be           │ 'LinearScale'}             │ explanation               │
   │ 'MultipleChoice'}          │ selected.', 'class_name': │                            │ here>"}\n\nYou must       │
   │                            │ 'MultipleChoice'}         │                            │ select exactly 2          │
   │                            │                           │                            │ options.\n        Before  │
   │                            │                           │                            │ the question you are now  │
   │                            │                           │                            │ answering, you already    │
   │                            │                           │                            │ answered the following    │
   │                            │                           │                            │ question(s):\n            │
   │                            │                           │                            │ \tQuestion: What is your  │
   │                            │                           │                            │ favorite                  │
   │                            │                           │                            │ color?\n\tAnswer: Blue',  │
   │                            │                           │                            │ 'class_name': 'TopK'}     │
   └────────────────────────────┴───────────────────────────┴────────────────────────────┴───────────────────────────┘



Memory collection 
^^^^^^^^^^^^^^^^^
The `add_memory_collection()` method is used to add sets of prior questions and answers to a given question.
We pass it the question to be answered and the list of questions/answers to be remembered when answering it.
For example, we can add the questions/answers for both q1 and q2 when prompting the agent to answer q4:

.. code-block:: python

   survey = Survey(questions = [q1, q2, q3, q4])
   survey = survey.add_memory_collection(q4, [q1, q2])

.. code-block:: python

   results = survey.run()
   results.select("color_user_prompt", "day_user_prompt", "winter_user_prompt", "birds_user_prompt").print(format="rich")

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃ prompt                     ┃ prompt                    ┃ prompt                     ┃ prompt                    ┃
   ┃ .color_user_prompt         ┃ .day_user_prompt          ┃ .winter_user_prompt        ┃ .birds_user_prompt        ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ {'text': 'You are being    │ {'text': 'You are being   │ {'text': 'You are being    │ {'text': 'You are being   │
   │ asked the following        │ asked the following       │ asked the following        │ asked the following       │
   │ question: What is your     │ question: What is your    │ question: How much do you  │ question: Which birds do  │
   │ favorite color?\nThe       │ favorite day of the       │ enjoy winter?\nThe options │ you like best?\nThe       │
   │ options are\n\n0:          │ week?\nThe options        │ are\n\n0: 0\n\n1: 1\n\n2:  │ options are\n\n0:         │
   │ Red\n\n1: Orange\n\n2:     │ are\n\n0: Sun\n\n1:       │ 2\n\n3: 3\n\n4: 4\n\n5:    │ Parrot\n\n1: Osprey\n\n2: │
   │ Yellow\n\n3: Green\n\n4:   │ Mon\n\n2: Tue\n\n3:       │ 5\n\nReturn a valid JSON   │ Falcon\n\n3: Eagle\n\n4:  │
   │ Blue\n\n5:                 │ Wed\n\n4: Thu\n\n5:       │ formatted like this,       │ First Robin of            │
   │ Purple\n\nReturn a valid   │ Fri\n\n6: Sat\n\nReturn a │ selecting only the code of │ Spring\n\nReturn a valid  │
   │ JSON formatted like this,  │ valid JSON formatted like │ the option (codes start at │ JSON formatted like this, │
   │ selecting only the number  │ this, selecting only the  │ 0):\n{"answer": <put       │ selecting only the number │
   │ of the option:\n{"answer": │ number of the             │ answer code here>,         │ of the                    │
   │ <put answer code here>,    │ option:\n{"answer": <put  │ "comment": "<put           │ option:\n{"answer": [<put │
   │ "comment": "<put           │ answer code here>,        │ explanation here>"}\nOnly  │ comma-separated list of   │
   │ explanation here>"}\nOnly  │ "comment": "<put          │ 1 option may be            │ answer codes here>],      │
   │ 1 option may be            │ explanation here>"}\nOnly │ selected.', 'class_name':  │ "comment": "<put          │
   │ selected.', 'class_name':  │ 1 option may be           │ 'LinearScale'}             │ explanation               │
   │ 'MultipleChoice'}          │ selected.', 'class_name': │                            │ here>"}\n\nYou must       │
   │                            │ 'MultipleChoice'}         │                            │ select exactly 2          │
   │                            │                           │                            │ options.\n        Before  │
   │                            │                           │                            │ the question you are now  │
   │                            │                           │                            │ answering, you already    │
   │                            │                           │                            │ answered the following    │
   │                            │                           │                            │ question(s):\n            │
   │                            │                           │                            │ \tQuestion: What is your  │
   │                            │                           │                            │ favorite                  │
   │                            │                           │                            │ color?\n\tAnswer:         │
   │                            │                           │                            │ Blue\n\n Prior questions  │
   │                            │                           │                            │ and answers:\tQuestion:   │
   │                            │                           │                            │ What is your favorite day │
   │                            │                           │                            │ of the week?\n\tAnswer:   │
   │                            │                           │                            │ Fri', 'class_name':       │
   │                            │                           │                            │ 'TopK'}                   │
   └────────────────────────────┴───────────────────────────┴────────────────────────────┴───────────────────────────┘
    

    
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
If you would like to sign up for alpha testing this and other new features, please complete the following survey which was created with this new method: [EDSL signup survey ](https://survey.expectedparrot.com/index.php/132345).


Learn more about specifying question scenarios, agents and language models and working with results in their respective modules:

* :ref:`scenarios`
* :ref:`agents`
* :ref:`language_models`
* :ref:`results`


Survey class
------------

.. automodule:: edsl.surveys.Survey
   :members: 
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members:

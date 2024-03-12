Quickstart tutorial
===================

This page shows some quickstart examples for constructing questions and surveys and administering
them to AI agents.

| Skip to section:
| `Creating questions`_
| `Parameterizing questions`_
| `Administering questions & surveys`_
| `Adding AI agents`_


.. _creating_questions:
Creating questions
------------------

.. _multiple-choice:
Multiple choice
^^^^^^^^^^^^^^^

This question type prompts the agent to select a single option from a range of options.

.. code-block:: python

    from edsl import QuestionMultipleChoice
    q_mc = QuestionMultipleChoice(
        question_name = "q_mc",
        question_text = "How often do you shop for clothes?",
        question_options = [
            "Rarely or never",
            "Annually",
            "Seasonally",
            "Monthly",
            "Daily"
        ]
    )

.. _checkbox:
Checkbox
^^^^^^^^

This question type prompts the agent to select one or more options from a range of options, which are returned as a list.
You can optionally specify the minimum and maximum number of options that can be selected.

.. code-block:: python

    from edsl import QuestionCheckBox
    q_cb = QuestionCheckBox(
        question_name = "q_cb",
        question_text = "Which of the following factors are important to you in making decisions about clothes shopping? Select all that apply.",
        question_options = [
            "Price",
            "Quality",
            "Brand Reputation",
            "Style and Design",
            "Fit and Comfort",
            "Customer Reviews and Recommendations",
            "Ethical and Sustainable Practices",
            "Return Policy",
            "Convenience",
            "Other"
        ],
        min_selection = 1, # This is optional
        max_selection = 3  # This is optional
    )

.. _freetext:
Free text 
^^^^^^^^^

This question type prompts the agent to format the response as unstructured text.

.. code-block:: python

    from edsl.questions import QuestionFreeText

    q_ft = QuestionFreeText(
        question_name = "q_ft",
        question_text = "What improvements would you like to see in clothing options for tall women?",
        allow_nonresponse = False,
    )

.. _linear_scale:
Linear scale
^^^^^^^^^^^^

This question type prompts the agent to select a single option from a range of integer values.

.. code-block:: python

    from edsl.questions import QuestionLinearScale

    q_ls = QuestionLinearScale(
        question_name = "q_ls",
        question_text = "On a scale of 0-10, how much do you typically enjoy clothes shopping? (0 = Not at all, 10 = Very much)",
        question_options = [0,1,2,3,4,5,6,7,8,9,10]
    )

.. _numerical:
Numerical
^^^^^^^^^

This question type prompts the agent to format the response as a number.

.. code-block:: python

    from edsl.questions import QuestionNumerical

    q_nu = QuestionNumerical(
        question_name = "q_nu",
        question_text = "Estimate the amount of money that you spent on clothing in the past year (in $USD)."
    )

.. _list:
List
^^^^

This question type prompts the agent to format the response as a list of items.

.. code-block:: python

    from edsl.questions import QuestionList

    q_li = QuestionList(
        question_name = "q_li",
        question_text = "What improvements would you like to see in clothing options for tall women?"
    )

.. _budget:
Budget
^^^^^^

This question prompts the agent to distribute a budget across a set of options.

.. code-block:: python

    from edsl.questions import QuestionBudget

    q_bg = QuestionBudget(
        question_name = "q_bg",
        question_text = "Estimate the percentage of your total time spent shopping for clothes in each of the following modes.",
        question_options=[
            "Online",
            "Malls",
            "Freestanding stores",
            "Mail order catalogs",
            "Other"
        ],
        budget_sum = 100,
    )



.. _administering_questions_surveys:
Administering questions & surveys
---------------------------------

Here we show how to administer each question to the default LLM. 
We do this by appending the `run()` method to a question. 
See also how to administer questions and surveys to specific agent personas and LLMs in 
example 
`Agents <https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Docs%20-%20Agents-7b70a3e973754f18b791250db5bd7933>`__
and 
`Surveys <https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Docs%20-%20Surveys-e6a1c6b358e4473289d97fa377002cd6>`__
.

.. _administer_question:
Administer a question independently
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    result_mc = q_mc.run()
    result_cb = q_cb.run()
    result_ls = q_ls.run()
    result_yn = q_yn.run()
    result_bg = q_bg.run()
    result_ft = q_ft.run()
    result_li = q_li.run()
    result_nu = q_nu.run()

.. _construct_survey:
Combine questions into a survey
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We can also combine the questions into a survey and administer them asynchronously (by default):

.. code-block:: python
    
    from edsl import Survey
    survey = Survey([q_mc, q_cb, q_ls, q_yn, q_bg, q_ft, q_li, q_nu])
    results = survey.run()

.. _add_memory:
Add question/answer memory
^^^^^^^^^^^^^^^^^^^^^^^^^^

If we want to include a question/answer context in a subsequent question, we can add a "memory" to 
a question. Here we include the question and response to q_mc in the prompt for q_cb:

.. code-block:: python

    survey.add_targeted_memory(q_cb, q_mc)



.. _parameterizing_questions:
Parameterizing questions
------------------------

We can create variations of questions by parameterizing them using the `Scenario` class.
Here we create versions of the free text question with a list of scenarios: 

.. code-block:: python

    from edsl import Scenario
    items = ["clothes", "shoes", "accessories"]
    scenarios = [Scenario({"item": i}) for i in items]
    q_ft = QuestionFreeText(
        question_name = "q_ft",
        question_text = "What improvements would you like to see in {{ item }} options for tall women?"
    )
    survey = Survey([q_ft])
    results = survey.by(scenarios).run()



.. _adding_agents:
Adding AI agents 
----------------

We use the `Agent` class to define an AI agent with a persona:

.. code-block:: python

    from edsl import Agent
    agent = Agent(traits = {"persona": "You are an expert in fashion and style."})

We assign the agent to the survey with the `by()` method:

.. code-block:: python

    results = survey.by(agent).run()
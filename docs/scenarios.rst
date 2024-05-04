.. _scenarios:

Scenarios
=========
A `Scenario` is a dictionary containing a single key/value pair that is used to parameterize a question.

Purpose 
-------
Scenarios are used to create variations and versions of questions with parameters that can be replaced with different values.
For example, we could create a question `"What is your favorite {{ item }}?"` and replace the parameter `item` with `color` or `food` or other items.
This allows us to straightforwardly administer multiple versions of the question, either asynchronously or according to other specified [survey rules](https://docs.expectedparrot.com/en/latest/surveys.html#applying-survey-rules).

Data labeling tasks
^^^^^^^^^^^^^^^^^^^
Scenarios are particularly useful for conducting data labeling or data coding tasks, where we can design the task as a question or series of questions that we prompt an agent to answer about each piece of data in our dataset.
For example, say we have a dataset of messages from users that we want to sort by topic.
We could create multiple choice questions such as `"What is the primary topic of this message: {{ message }}?"` or `"Does this message mention a safety issue? {{ message }}"` and replace the parameter `message` with each message in the dataset, generating a dataset of results that can be readily analyzed.

The following code demonstrates how to use scenarios to create a survey for this task.
For more step-by-step details, please also see `Constructing a Scenario` below it.

.. code-block:: python

    from edsl.questions import QuestionMultipleChoice
    from edsl import Survey, Scenario

    # Create a question with a parameter
    q1 = QuestionMultipleChoice(
        question_name = "topic",
        question_text = "What is the topic of this message: {{ message }}?",
        choices = ["Safety", "Product support", "Billing", "Login issue", "Other"]
    )

    q2 = QuestionMultipleChoice(
        question_name = "safety",
        question_text = "Does this message mention a safety issue? {{ message }}?",
        choices = ["Yes", "No", "Unclear"]
    )

    # Create a list of scenarios for the parameter
    messages = [
        "I can't log in...", 
        "I need help with my bill...", 
        "I have a safety concern...", 
        "I need help with a product..."
        ]
    scenarios = [Scenario({"message": message}) for message in messages]

    # Create a survey with the question
    survey = Survey(questions = [q1, q2])

    # Run the survey with the scenarios
    results = survey.by(scenarios).run()

To learn more about accessing, analyzing and visualizing survey results, please see the :ref:`results` section.

Constructing a Scenario
-----------------------
To use scenarios, we start by creating a question that takes a parameter in double braces: 

.. code-block:: python

    from edsl.questions import QuestionFreeText

    q = QuestionFreeText(
        question_name = "favorite_item",
        question_text = "What is your favorite {{ item }}?",
    )

Next we create a dictionary for the value that will replace the parameter and store it in a `Scenario` object: 

.. code-block:: python

    from edsl import Scenario 

    scenario = Scenario({"item": "color"})

If multiple values will be used, we can create a list of `Scenario` objects: 

.. code-block:: python

    scenarios = [Scenario({"item": item}) for item in ["color", "food"]]

Using Scenarios
---------------
`Scenario` objects are used by adding them to a question or survey with the `by` method when the question or survey is run:.
A scenario can be appended to a single question, for example:

.. code-block:: python

    from edsl import Survey
    
    survey = Survey(questions = [q])
    
    results = survey.by(scenario).run()

As with other survey components (agents and language models), multiple `Scenario` objects should be added together as a list in the same `by` method:

.. code-block:: python

    results = survey.by(scenarios).run()

To learn more about constructing surveys, please see the :ref:`surveys` module.

Scenario class
--------------

.. automodule:: edsl.scenarios.Scenario
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: 

ScenarioList class
------------------

.. automodule:: edsl.scenarios.ScenarioList
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: 
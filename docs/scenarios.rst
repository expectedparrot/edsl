.. _scenarios:

Scenarios
=========

.. A Scenario is a dictionary with a key/value to parameterize a question.

Constructing a Scenario
-----------------------
Key steps:

* Create a question that takes a parameter in double braces, e.g.: 

.. code-block:: python

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

* Add the Scenario objects to the question when you run it with the `by` method: 

.. code-block:: python

    results = q.by(scenarios).run()

If your question is part of a survey, add the Scenario objects to the survey: 

.. code-block:: python

    q1 = ...
    q2 = ...
    results = Survey([q1, q2]).by(scenarios).run()

As with other Survey components (agents, language models), multiple Scenario objects should be added together as a list in the same `by` method.

See more details about surveys in the :ref:`surveys` module.

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
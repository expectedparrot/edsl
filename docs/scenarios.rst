.. _scenarios:

Scenarios
=========
A `Scenario` is a dictionary containing a single key/value pair that is used to parameterize a question.
A `ScenarioList` is a list of `Scenario` objects that can be used to create multiple versions of a question with different parameters, that can all be administered at once.

Constructing a Scenario
-----------------------
To use scenarios, we start by creating a question that takes a parameter in double braces: 

.. code-block:: python

    q = QuestionFreeText(
        question_name = "favorite_item",
        question_text = "What is your favorite {{ item }}?",
    )

Next we create a dictionary for the value that will replace the parameter and store it in a `Scenario` object: 

.. code-block:: python

    scenario = Scenario({"item": "color"})

If multiple values will be used, we can create a list of `Scenario` objects: 

.. code-block:: python

    scenarios = [Scenario({"item": item}) for item in ["color", "food"]]

Using Scenarios
---------------
`Scenario` objects are used by adding them to a question or survey with the `by` method when the question or survey is run:.
A scenario can be appended to a single question, for example:

.. code-block:: python

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
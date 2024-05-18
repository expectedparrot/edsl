.. _scenarios:

Scenarios
=========
A `Scenario` is a dictionary containing a key/value pair that is used to parameterize one or more questions in a survey, replacing a parameter in a question with a specific value.

Purpose 
-------
Scenarios allow you create variations and versions of questions efficiently.
For example, we could create a question `"What is your favorite {{ item }}?"` and use scenarios to replace the parameter `item` with `color` or `food` or other items.
When we add the scenarios to the question, the question will be asked multiple times, once for each scenario, with the parameter replaced by the value in the scenario.
This allows us to straightforwardly administer multiple versions of the question together in a survey, either asynchronously (by default) or according to :ref:`surveys` rules that we can specify (e.g., skip/stop logic).

Metadata
^^^^^^^^
Scenarios are also a convenient way to keep track of metadata or other information relating to our survey questions that is important to our analysis of the results.
For example, say we are using scenarios to parameterize questions with pieces of `{{ content }}` from a dataset.
In our scenarios for the `content` parameter, we could also include metadata about the source of the content, such as the `{{ author }}`, the `{{ publication_date }}`, or the `{{ source }}`.
This will create columns for the additional data in the survey results without passing them to the question texts if there is no corresponding parameter in the question texts.
This allows us to analyze the responses in the context of the metadata without needing to match up the data with the metadata post-survey.

Data labeling tasks
^^^^^^^^^^^^^^^^^^^
Scenarios are particularly useful for conducting data labeling or data coding tasks, where we can design the task as a question or series of questions about each piece of data in our dataset.
For example, say we have a dataset of text messages that we want to sort by topic.
We could perform this task by running multiple choice questions such as `"What is the primary topic of this message: {{ message }}?"` or `"Does this message mention a safety issue? {{ message }}"` where each text message is inserted in the `message` placeholder of the question text.

The following code demonstrates how to use scenarios to conduct this task.
For more step-by-step details, please also see `Constructing a Scenario` below it.

.. code-block:: python

    from edsl.questions import QuestionMultipleChoice
    from edsl import Survey, Scenario

    # Create a question with a parameter
    q1 = QuestionMultipleChoice(
        question_name = "topic",
        question_text = "What is the topic of this message: {{ message }}?",
        question_options = ["Safety", "Product support", "Billing", "Login issue", "Other"]
    )

    q2 = QuestionMultipleChoice(
        question_name = "safety",
        question_text = "Does this message mention a safety issue? {{ message }}?",
        question_options = ["Yes", "No", "Unclear"]
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


We can then analyze the results to see how the agent answered the questions for each scenario:

.. code-block:: python

    results.select("message", "topic", "safety").print(format="rich")


This will print a table of the scenarios and the answers to the questions for each scenario:

.. code-block:: text

    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
    ┃ scenario                      ┃ answer  ┃ answer          ┃
    ┃ .message                      ┃ .safety ┃ .topic          ┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
    │ I can't log in...             │ No      │ Login issue     │
    ├───────────────────────────────┼─────────┼─────────────────┤
    │ I need help with my bill...   │ No      │ Billing         │
    ├───────────────────────────────┼─────────┼─────────────────┤
    │ I have a safety concern...    │ Yes     │ Safety          │
    ├───────────────────────────────┼─────────┼─────────────────┤
    │ I need help with a product... │ Unclear │ Product support │
    └───────────────────────────────┴─────────┴─────────────────┘


Adding metadata
^^^^^^^^^^^^^^^
If we have metadata about the messages that we want to keep track of, we can add it to the scenarios as well.
This will create additional columns for the metadata in the results dataset, but without the need to include it in our question texts.
Here we modify the above example to use a dataset of messages with metadata. 
Note that the question texts are unchanged:

.. code-block:: python

    from edsl.questions import QuestionMultipleChoice
    from edsl import Survey, Scenario

    # Create a question with a parameter
    q1 = QuestionMultipleChoice(
        question_name = "topic",
        question_text = "What is the topic of this message: {{ message }}?",
        question_options = ["Safety", "Product support", "Billing", "Login issue", "Other"]
    )

    q2 = QuestionMultipleChoice(
        question_name = "safety",
        question_text = "Does this message mention a safety issue? {{ message }}?",
        question_options = ["Yes", "No", "Unclear"]
    )

    # Create scenarios for the sets of parameters
    user_messages = [
        {"message": "I can't log in...", "user": "Alice", "source": "Customer support", "date": "2022-01-01"}, 
        {"message": "I need help with my bill...", "user": "Bob", "source": "Phone", "date": "2022-01-02"}, 
        {"message": "I have a safety concern...", "user": "Charlie", "source": "Email", "date": "2022-01-03"}, 
        {"message": "I need help with a product...", "user": "David", "source": "Chat", "date": "2022-01-04"}
        ]
    scenarios = [Scenario({"message": msg["message"], 
                        "user": msg["user"],
                        "source": msg["source"],
                        "date": msg["date"]}) for msg in user_messages]

    # Create a survey with the question
    survey = Survey(questions = [q1, q2])

    # Run the survey with the scenarios
    results = survey.by(scenarios).run()


We can then analyze the results to see how the agent answered the questions for each scenario, including the metadata:

.. code-block:: text

    ┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
    ┃ scenario ┃ scenario         ┃ scenario   ┃ scenario                      ┃ answer  ┃ answer          ┃
    ┃ .user    ┃ .source          ┃ .date      ┃ .message                      ┃ .safety ┃ .topic          ┃
    ┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
    │ Alice    │ Customer support │ 2022-01-01 │ I can't log in...             │ No      │ Login issue     │
    ├──────────┼──────────────────┼────────────┼───────────────────────────────┼─────────┼─────────────────┤
    │ Bob      │ Phone            │ 2022-01-02 │ I need help with my bill...   │ No      │ Billing         │
    ├──────────┼──────────────────┼────────────┼───────────────────────────────┼─────────┼─────────────────┤
    │ Charlie  │ Email            │ 2022-01-03 │ I have a safety concern...    │ Yes     │ Safety          │
    ├──────────┼──────────────────┼────────────┼───────────────────────────────┼─────────┼─────────────────┤
    │ David    │ Chat             │ 2022-01-04 │ I need help with a product... │ Unclear │ Product support │
    └──────────┴──────────────────┴────────────┴───────────────────────────────┴─────────┴─────────────────┘


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


Next we create a dictionary for a value that will replace the parameter and store it in a `Scenario` object: 

.. code-block:: python

    from edsl import Scenario 

    scenario = Scenario({"item": "color"})


If multiple values will be used, we can create a list of `Scenario` objects: 

.. code-block:: python

    scenarios = [Scenario({"item": item}) for item in ["color", "food"]]


Using Scenarios
---------------
`Scenario` objects are used by adding them to a question or survey with the `by()` method when the question or survey is run.
Here we add a single scenario to our question, run it, and inspect the response:

.. code-block:: python

    results = q.by(scenario).run()

    results.select("item", "favorite_item").print(format="rich")


This will print a table of the selected components of the results:

.. code-block:: text

    ┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ scenario ┃ answer                                                                                               ┃
    ┃ .item    ┃ .favorite_item                                                                                       ┃
    ┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ color    │ Blue is my favorite color for its calming and serene qualities.                                      │
    ├──────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────┤
    │ food     │ My favorite food is a classic Italian pizza with a thin crust, topped with mozzarella, fresh basil,  │
    │          │ and a rich tomato sauce.                                                                             │
    └──────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────┘


If we have multiple scenarios, we can add them to the survey in the same way:

As with other survey components (agents and language models), multiple `Scenario` objects should be added together as a list in the same `by` method:

.. code-block:: python

    results = q.by(scenarios).run()

    results.select("item", "favorite_item").print(format="rich")


Now we will see both scenarios in our results table:

.. code-block:: text

    ┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ scenario ┃ answer                                                                                               ┃
    ┃ .item    ┃ .favorite_item                                                                                       ┃
    ┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ color    │ Blue is my favorite color for its calming and serene qualities.                                      │
    ├──────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────┤
    │ food     │ My favorite food is a classic Italian pizza with a thin crust, topped with mozzarella, fresh basil,  │
    │          │ and a rich tomato sauce.                                                                             │
    └──────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────┘


If we have multiple questions in a survey, we can add scenarios to the survey in the same way:

.. code-block:: python

    from edsl.questions import QuestionFreeText, QuestionList
    from edsl import Survey, Scenario

    q1 = QuestionFreeText(
        question_name = "favorite_item",
        question_text = "What is your favorite {{ item }}?",
    )
    q2 = QuestionList(
        question_name = "items_list",
        question_text = "What are some of your favorite {{ item }} preferences?",
        
    )

    survey = Survey(questions = [q1, q2])

    scenarios = [Scenario({"item": item}) for item in ["color", "food"]]

    results = survey.by(scenarios).run()

    results.select("item", "favorite_item", "items_list").print(format="rich")


This will print a table of the responses for each scenario for each question:

.. code-block:: text

    ┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ scenario ┃ answer                                            ┃ answer                                           ┃
    ┃ .item    ┃ .favorite_item                                    ┃ .items_list                                      ┃
    ┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ color    │ Blue is my favorite color for its calming and     │ ['Blue', 'Green', 'Burgundy']                    │
    │          │ serene qualities.                                 │                                                  │
    ├──────────┼───────────────────────────────────────────────────┼──────────────────────────────────────────────────┤
    │ food     │ My favorite food is a classic Italian pizza with  │ ['Italian cuisine', 'Sushi', 'Mexican food',     │
    │          │ a thin crust, topped with mozzarella, fresh       │ 'Dark chocolate', 'Avocado toast']               │
    │          │ basil, and a rich tomato sauce.                   │                                                  │
    └──────────┴───────────────────────────────────────────────────┴──────────────────────────────────────────────────┘


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
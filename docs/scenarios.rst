.. _scenarios:

Scenarios
=========

A `Scenario` is a dictionary containing a key/value pair that is used to parameterize one or more questions in a survey, replacing a parameter in a question with a specific value.
A `ScenarioList` is a list of `Scenario` objects.

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


We can inspect the scenarios to see that they have been created correctly:

.. code-block:: python

    scenarios 


This will return:

.. code-block:: python

    [Scenario({'item': 'color'}), Scenario({'item': 'food'})]


ScenarioList
^^^^^^^^^^^^

We can also create a `ScenarioList` object to store multiple scenarios:

.. code-block:: python

    from edsl import ScenarioList

    scenariolist = ScenarioList([Scenario({"item": item}) for item in ["color", "food"]])


To inspect the scenarios, we can print them:

.. code-block:: python

    scenariolist


This will return:

.. code-block:: python

    {
        "scenarios": [
            {
                "item": "color"
            },
            {
                "item": "food"
            }
        ]
    }


We can also create a `Scenario` for `question_options`, e.g., in a multiple choice, checkbox, linear scale or other question type that requires them:

.. code-block:: python

    from edsl import QuestionMultipleChoice, Scenario

    q = QuestionMultipleChoice(
        question_name = "capital_of_france",
        question_text = "What is the capital of France?", 
        question_options = "{{question_options}}"
    )

    s = Scenario({'question_options': ['Paris', 'London', 'Berlin', 'Madrid']})

    results = q.by(s).run()

    results.select("answer.*").print(format="rich")


Output:

.. code-block:: text

    ┏━━━━━━━━━━━━━━━━━━━━┓
    ┃ answer             ┃
    ┃ .capital_of_france ┃
    ┡━━━━━━━━━━━━━━━━━━━━┩
    │ Paris              │
    └────────────────────┘


Combining Scenarios 
-------------------

We can combine multiple scenarios into a single `Scenario` object:

.. code-block:: python

    from edsl import Scenario

    scenario1 = Scenario({"food": "apple"})
    scenario2 = Scenario({"drink": "water"})

    combined_scenario = scenario1 + scenario2

    combined_scenario


This will return:

.. code-block:: python

    {
        "food": "apple",
        "drink": "water"
    }


We can also combine `ScenarioList` objects:

.. code-block:: python

    from edsl import ScenarioList

    scenariolist1 = ScenarioList([Scenario({"food": "apple"}), Scenario({"drink": "water"})])
    scenariolist2 = ScenarioList([Scenario({"color": "red"}), Scenario({"shape": "circle"})])

    combined_scenariolist = scenariolist1 + scenariolist2

    combined_scenariolist


This will return:

.. code-block:: python

    {
        "scenarios": [
            {
                "food": "apple"
            },
            {
                "drink": "water"
            },
            {
                "color": "red"
            },
            {
                "shape": "circle"
            }
        ]
    }


We can create a cross product of `ScenarioList` objects (combine the scenarios in each list with each other):

.. code-block:: python

    from edsl import ScenarioList

    scenariolist1 = ScenarioList([Scenario({"food": "apple"}), Scenario({"drink": "water"})])
    scenariolist2 = ScenarioList([Scenario({"color": "red"}), Scenario({"shape": "circle"})])

    cross_product_scenariolist = scenariolist1 * scenariolist2

    cross_product_scenariolist


This will return:

.. code-block:: python

    {
        "scenarios": [
            {
                "food": "apple",
                "color": "red"
            },
            {
                "food": "apple",
                "shape": "circle"
            },
            {
                "drink": "water",
                "color": "red"
            },
            {
                "drink": "water",
                "shape": "circle"
            }
        ]
    }


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


Turning results into scenarios 
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The method `to_scenario_list()` can be used to turn the results of a survey into a list of scenarios.

Example usage:

Say we have some results from a survey where we asked agents to choose a random number between 1 and 1000:

.. code-block:: python

    from edsl.questions import QuestionNumerical
    from edsl import Agent

    q_random = QuestionNumerical(
        question_name = "random",
        question_text = "Choose a random number between 1 and 1000."
    )

    agents = [Agent({"persona":p}) for p in ["Dog catcher", "Magician", "Spy"]]

    results = q_random.by(agents).run()
    results.select("persona", "random").print(format="rich")


Our results are:

.. code-block:: text

    ┏━━━━━━━━━━━━━┳━━━━━━━━━┓
    ┃ agent       ┃ answer  ┃
    ┃ .persona    ┃ .random ┃
    ┡━━━━━━━━━━━━━╇━━━━━━━━━┩
    │ Dog catcher │ 472     │
    ├─────────────┼─────────┤
    │ Magician    │ 537     │
    ├─────────────┼─────────┤
    │ Spy         │ 528     │
    └─────────────┴─────────┘


We can use the `to_scenario_list()` method turn components of the results into a list of scenarios to use in a new survey:

.. code-block:: python

    scenarios = results.to_scenario_list()

    scenarios 


We can inspect the scenarios to see that they have been created correctly:

.. code-block:: text

    [Scenario({'persona': 'Dog catcher', 'random': 472}),
    Scenario({'persona': 'Magician', 'random': 537}),
    Scenario({'persona': 'Spy', 'random': 528})]



Data labeling tasks
-------------------
Scenarios are particularly useful for conducting data labeling or data coding tasks, where we can design the task as a question or series of questions about each piece of data in our dataset.
For example, say we have a dataset of text messages that we want to sort by topic.
We could perform this task by running multiple choice questions such as `"What is the primary topic of this message: {{ message }}?"` or `"Does this message mention a safety issue? {{ message }}"` where each text message is inserted in the `message` placeholder of the question text.

The following code demonstrates how to use scenarios to conduct this task.
For more step-by-step details, please see the next section below: `Constructing a Scenario`.

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



Slicing/chunking content into scenarios
---------------------------------------

We can use the `Scenario` method `chunk()` to slice a text scenario into a `ScenarioList` based on `num_words` or `num_lines`.

Example usage:

.. code-block:: python

    my_haiku = """
    This is a long text. 
    Pages and pages, oh my!
    I need to chunk it.
    """

    text_scenario = Scenario({"my_text": my_haiku})

    word_chunks_scenariolist = text_scenario.chunk("my_text", 
                                                num_words = 5, # use num_words or num_lines but not both
                                                include_original = True, # optional 
                                                hash_original = True # optional
    )
    word_chunks_scenariolist

This will return:

.. code-block:: text 

    {
        "scenarios": [
            {
                "my_text": "This is a long text.",
                "my_text_chunk": 0,
                "my_text_original": "4aec42eda32b7f32bde8be6a6bc11125"
            },
            {
                "my_text": "Pages and pages, oh my!",
                "my_text_chunk": 1,
                "my_text_original": "4aec42eda32b7f32bde8be6a6bc11125"
            },
            {
                "my_text": "I need to chunk it.",
                "my_text_chunk": 2,
                "my_text_original": "4aec42eda32b7f32bde8be6a6bc11125"
            }
        ]
    }


Creating scenarios for files and images
---------------------------------------

PDFs as textual scenarios
^^^^^^^^^^^^^^^^^^^^^^^^^
The `ScenarioList` method `from_pdf('path/to/pdf')` is a convenient way to extract information from large files.
It allows you to read in a PDF and automatically create a list of textual scenarios for the pages of the file.
Each scenario has the following keys: `filename`, `page`, `text`.

*How it works:* Add a placeholder `{{ text }}` to a question text to use the text of a PDF page as a parameter in the question.
When you run the survey with the PDF scenarios, the text of each page will be inserted into the question text in place of the placeholder.

Example usage:

.. code-block:: python

    from edsl.questions import QuestionFreeText
    from edsl import ScenarioList, Survey

    # Create a survey of questions parameterized by the {{ text }} of the PDF pages:
    q1 = QuestionFreeText(
        question_name = "themes",
        question_text = "Identify the key themes mentioned on this page: {{ text }}",
    )

    q2 = QuestionFreeText(
        question_name = "idea",
        question_text = "Identify the most important idea on this page: {{ text }}",
    )

    survey = Survey([q1, q2])

    scenarios = ScenarioList.from_pdf("path/to/pdf_file.pdf")

    # Run the survey with the pages of the PDF as scenarios:
    results = survey.by(scenarios).run()

    # To print the page and text of each PDF page scenario together with the answers to the question:
    results.select("page", "text", "answer.*").print(format="rich")


See a demo notebook of this method in the notebooks section of the docs index: "Extracting information from PDFs".


Image scenarios
^^^^^^^^^^^^^^^
The `Scenario` method `from_image('path/to/image_file')` turns a PNG into into a scenario to be used with an image model (e.g., GPT-4o).
The scenario has the following keys: `file_path`, `encoded_image`.

Note that we do not need to use a placeholder `{{ text }}` in the question text in order to add the scenario to the question.
Instead, we simply write the question with no parameters and add the scenario to the survey when running it as usual.

Example usage:

.. code-block:: python

    from edsl.questions import QuestionFreeText, QuestionList
    from edsl import Scenario, Survey, Model 

    m = Model("gpt-4o") # Need to use a vision model for image scenarios

    q1 = QuestionFreeText(
        question_name = "show",
        question_text = "What does this image show?",
    )

    q2 = QuestionList(
        question_name = "count",
        question_text = "How many things are in this image?",
    )

    survey = Survey([q1, q2])

    scenario = Scenario.from_image("path/to/image_file")

    results = survey.by(scenario).run()

    results.select("file_path", "answer.*").print(format="rich")






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
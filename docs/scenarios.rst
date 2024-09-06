.. _scenarios:

Scenarios
=========

A `Scenario` is a dictionary containing a key/value pair that is used to add data or content to questions in a survey, replacing a parameter in a question with a specific value.
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

To use a scenario, we start by creating a question that takes a parameter in double braces: 

.. code-block:: python

    from edsl import QuestionFreeText

    q = QuestionFreeText(
        question_name = "favorite_item",
        question_text = "What is your favorite {{ item }}?",
    )


Next we create a dictionary for a value that will replace the parameter and store it in a `Scenario` object: 

.. code-block:: python

    from edsl import Scenario 

    scenario = Scenario({"item": "color"})


We can inspect the scenario and see that it consists of the key/value pair that we created:

.. code-block:: python

    scenario


This will return:

.. code-block:: python

    {
        "item": "color"
    }


ScenarioList 
^^^^^^^^^^^^

If multiple values will be used, we can create a list of `Scenario` objects:

.. code-block:: python

    scenarios = [Scenario({"item": item}) for item in ["color", "weekday"]]


We can inspect the scenarios:

.. code-block:: python

    scenarios 


This will return:

.. code-block:: python

    [Scenario({'item': 'color'}), Scenario({'item': 'weekday'})]


We can also create a `ScenarioList` object to store multiple scenarios:

.. code-block:: python

    from edsl import ScenarioList

    scenariolist = ScenarioList([Scenario({"item": item}) for item in ["color", "weekday"]])


We can inspect it:

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
                "item": "weekday"
            }
        ]
    }


Using a Scenario
----------------

We use a scenario (or scenariolist) by adding it to a question (or a survey of questions), either when constructing the question or else when running it.

We use the `by()` method to add a scenario to a question when running it:

.. code-block:: python

    from edsl import QuestionFreeText, Scenario

    q = QuestionFreeText(
        question_name = "favorite_item",
        question_text = "What is your favorite {{ item }}?",
    )

    scenario = Scenario({"item": "color"})

    results = q.by(scenario).run()


We can check the results to verify that the scenario has been used correctly:

.. code-block:: python

    results.select("item", "favorite_item").print(format="rich")


This will print a table of the selected components of the results:

.. code-block:: text

    ┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ scenario ┃ answer                     ┃
    ┃ .item    ┃ .favorite_item             ┃
    ┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ color    │ My favorite color is blue. │
    └──────────┴────────────────────────────┘


We use the `loop()` method To add a scenario to a question when constructing it, passing a `ScenarioList`. 
This will create a list containing a new question for each scenario that was passed.
Note that we can optionally include the scenario key in the question name as well; otherwise a unique identifies is automatically added to each question name.

.. code-block:: python

    from edsl import QuestionFreeText, ScenarioList

    q = QuestionFreeText(
        question_name = "favorite_{{ item }}",
        question_text = "What is your favorite {{ item }}?",
    )

    scenariolist = ScenarioList(
        Scenario({"item": item}) for item in ["color", "weekday"]
    )

    questions = q.loop(scenariolist)


We can inspect the questions to see that they have been created correctly:

.. code-block:: python

    questions


This will return:

.. code-block:: python

    [Question('free_text', question_name = """favorite_color""", question_text = """What is your favorite color?"""),
    Question('free_text', question_name = """favorite_weekday""", question_text = """What is your favorite weekday?""")]


We can pass the questions to a survey and run it:

.. code-block:: python

    results = Survey(questions = questions).run()

    results.select("answer.*").print(format="rich")


This will print a table of the response for each question:

.. code-block:: text

    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ answer                     ┃ answer                                                                             ┃
    ┃ .favorite_color            ┃ .favorite_weekday                                                                   ┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ My favorite color is blue. │ My favorite weekday is Friday because it marks the end of the workweek and the     │
    │                            │ beginning of the weekend, offering a sense of relief and anticipation for leisure  │
    │                            │ time.                                                                              │
    └────────────────────────────┴────────────────────────────────────────────────────────────────────────────────────┘


Multiple parameters
^^^^^^^^^^^^^^^^^^^

We can also create a `Scenario` for multiple parameters:

.. code-block:: python

    from edsl import QuestionFreeText

    q = QuestionFreeText(
        question_name = "counting",
        question_text = "How many {{ unit }} are in a {{ distance }}?",
    )

    scenario = Scenario({"unit": "inches", "distance": "mile"})

    results = q.by(scenario).run()

    results.select("unit", "distance", "counting").print(format="rich")


This will print a table of the selected components of the results:

.. code-block:: text

    ┏━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ scenario ┃ scenario  ┃ answer                             ┃
    ┃ .unit    ┃ .distance ┃ .counting                          ┃
    ┡━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ inches   │ mile      │ There are 63,360 inches in a mile. │
    └──────────┴───────────┴────────────────────────────────────┘


To learn more about constructing surveys, please see the :ref:`surveys` module.


Scenarios for question options
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In the above examples we created scenarios in the `question_text`.
We can also create a `Scenario` for `question_options`, e.g., in a multiple choice, checkbox, linear scale or other question type that requires them:

.. code-block:: python

    from edsl import QuestionMultipleChoice, Scenario

    q = QuestionMultipleChoice(
        question_name = "capital_of_france",
        question_text = "What is the capital of France?", 
        question_options = "{{ question_options }}"
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


Creating scenarios from a dataset
---------------------------------

There are a variety of methods for creating and working with scenarios generated from datasets and different data types.


Turning results into scenarios 
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The method `to_scenario_list()` can be used to turn the results of a survey into a list of scenarios.

Example usage:

Say we have some results from a survey where we asked agents to choose a random number between 1 and 1000:

.. code-block:: python

    from edsl import QuestionNumerical, Agent

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


PDFs as textual scenarios
^^^^^^^^^^^^^^^^^^^^^^^^^

The `ScenarioList` method `from_pdf('path/to/pdf')` is a convenient way to extract information from large files.
It allows you to read in a PDF and automatically create a list of textual scenarios for the pages of the file.
Each scenario has the following keys: `filename`, `page`, `text` which can be used as a parameter in a question (or stored as metadat), and renamed as desired.

*How it works:* Add a placeholder `{{ text }}` to a question text to use the text of a PDF page as a parameter in the question.
When you run the survey with the PDF scenarios, the text of each page will be inserted into the question text in place of the placeholder.

Example usage:

.. code-block:: python

    from edsl import QuestionFreeText, ScenarioList, Survey

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

Note that we do *not* need to use a placeholder `{{ text }}` in the question text in order to add the scenario to the question.
Instead, we simply write the question with no parameters and add the scenario to the survey when running it as usual.

Example usage:

.. code-block:: python

    from edsl import QuestionFreeText, QuestionList, Scenario, Survey, Model 

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


Creating a scenario list from a list
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The `ScenarioList` method `from_list()` can be used to create a list of scenarios for a specified key and list of values that is passed.

Example usage:

.. code-block:: python

    from edsl import ScenarioList

    scenariolist = ScenarioList.from_list("item", ["color", "food", "animal"])

    scenariolist


This will return:

.. code-block:: text

    {
        "scenarios": [
            {
                "item": "color"
            },
            {
                "item": "food"
            },
            {
                "item": "animal"
            }
        ]
    }


Creating a scenario list from a dictionary
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The `ScenarioList` method `from_dict()` can be used to create a list of scenarios for a specified key and dictionary of values that is passed.

Example usage:

.. code-block:: python

    from edsl import ScenarioList

    scenariolist = ScenarioList.from_dict({"item": ["color", "food", "animal"]})

    scenariolist


This will return:

.. code-block:: text

    {
        "scenarios": [
            {
                "item": "color"
            },
            {
                "item": "food"
            },
            {
                "item": "animal"
            }
        ]
    }


Creating a scenario list from a Wikipedia table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The `ScenarioList` method `from_wikipedia_table('url')` can be used to create a list of scenarios from a Wikipedia table.

Example usage:

.. code-block:: python

    from edsl import ScenarioList

    scenariolist = ScenarioList.from_wikipedia("https://en.wikipedia.org/wiki/Fortune_500", 0)

    scenariolist.print()


This will return a list of scenarios for the first table on the Wikipedia page:

.. code-block:: text

    ┏━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
    ┃ Rank ┃ Company              ┃ State          ┃ Industry                                 ┃ Revenue in USD ┃
    ┡━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
    │ 1    │ Walmart              │ Arkansas       │ General Merchandisers                    │ $648.1 billion │
    ├──────┼──────────────────────┼────────────────┼──────────────────────────────────────────┼────────────────┤
    │ 2    │ Amazon               │ Washington     │ Internet Services and Retailing          │ $574.8 billion │
    ├──────┼──────────────────────┼────────────────┼──────────────────────────────────────────┼────────────────┤
    │ 3    │ Apple                │ California     │ Computers, Office Equipment              │ $383.3 billion │
    ├──────┼──────────────────────┼────────────────┼──────────────────────────────────────────┼────────────────┤
    │ 4    │ UnitedHealth Group   │ Minnesota      │ Health Care: Insurance and Managed Care  │ $371.6 billion │
    ├──────┼──────────────────────┼────────────────┼──────────────────────────────────────────┼────────────────┤
    │ 5    │ Berkshire Hathaway   │ Nebraska       │ Insurance: Property and Casualty (stock) │ $364.5 billion │
    ├──────┼──────────────────────┼────────────────┼──────────────────────────────────────────┼────────────────┤
    │ 6    │ CVS Health           │ Rhode Island   │ Health Care: Pharmacy and Other Services │ $357.8 billion │
    ├──────┼──────────────────────┼────────────────┼──────────────────────────────────────────┼────────────────┤
    │ 7    │ ExxonMobil           │ Texas          │ Petroleum Refining                       │ $344.6 billion │
    ├──────┼──────────────────────┼────────────────┼──────────────────────────────────────────┼────────────────┤
    │ 8    │ Alphabet Inc.        │ California     │ Internet Services and Retailing          │ $307.4 billion │
    ├──────┼──────────────────────┼────────────────┼──────────────────────────────────────────┼────────────────┤
    │ 9    │ McKesson Corporation │ Texas          │ Wholesalers: Health Care                 │ $276.7 billion │
    ├──────┼──────────────────────┼────────────────┼──────────────────────────────────────────┼────────────────┤
    │ 10   │ Cencora              │ Pennsylvania   │ Wholesalers: Health Care                 │ $262.2 billion │
    ├──────┼──────────────────────┼────────────────┼──────────────────────────────────────────┼────────────────┤
    │ 11   │ Costco               │ Washington     │ General Merchandisers                    │ $242.3 billion │
    ├──────┼──────────────────────┼────────────────┼──────────────────────────────────────────┼────────────────┤
    │ 12   │ JPMorgan Chase       │ New York       │ Commercial Banks                         │ $239.4 billion │
    ├──────┼──────────────────────┼────────────────┼──────────────────────────────────────────┼────────────────┤
    │ 13   │ Microsoft            │ Washington     │ Computer Software                        │ $211.9 billion │
    ├──────┼──────────────────────┼────────────────┼──────────────────────────────────────────┼────────────────┤
    │ 14   │ Cardinal Health      │ Ohio           │ Wholesalers: Health Care                 │ $205.0 billion │
    ├──────┼──────────────────────┼────────────────┼──────────────────────────────────────────┼────────────────┤
    │ 15   │ Chevron Corporation  │ California     │ Petroleum Refining                       │ $200.9 billion │
    ├──────┼──────────────────────┼────────────────┼──────────────────────────────────────────┼────────────────┤
    │ 16   │ Cigna                │ Connecticut    │ Health Care: Pharmacy and Other Services │ $195.3 billion │
    ├──────┼──────────────────────┼────────────────┼──────────────────────────────────────────┼────────────────┤
    │ 17   │ Ford Motor Company   │ Michigan       │ Motor Vehicles & Parts                   │ $176.2 billion │
    ├──────┼──────────────────────┼────────────────┼──────────────────────────────────────────┼────────────────┤
    │ 18   │ Bank of America      │ North Carolina │ Commercial Banks                         │ $171.9 billion │
    ├──────┼──────────────────────┼────────────────┼──────────────────────────────────────────┼────────────────┤
    │ 19   │ General Motors       │ Michigan       │ Motor Vehicles & Parts                   │ $171.8 billion │
    ├──────┼──────────────────────┼────────────────┼──────────────────────────────────────────┼────────────────┤
    │ 20   │ Elevance Health      │ Indiana        │ Health Care: Insurance and Managed Care  │ $171.3 billion │
    └──────┴──────────────────────┴────────────────┴──────────────────────────────────────────┴────────────────┘


The scenario list can be used in a survey to ask questions about the data in the table.

.. code-block:: python

    from edsl import QuestionFreeText, Survey

    q = QuestionFreeText(
        question_name = "company",
        question_text = "What industry is {{ Company }} in?",
    )

    survey = Survey([q])

    results = survey.by(scenariolist).run()

    (results.select("Company", "Industry").print(format="rich")


Example output:

.. code-block:: text

    ┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ scenario             ┃ scenario                                 ┃
    ┃ .Company             ┃ .Industry                                ┃
    ┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ Alphabet Inc.        │ Internet Services and Retailing          │
    ├──────────────────────┼──────────────────────────────────────────┤
    │ Amazon               │ Internet Services and Retailing          │
    ├──────────────────────┼──────────────────────────────────────────┤
    │ Apple                │ Computers, Office Equipment              │
    ├──────────────────────┼──────────────────────────────────────────┤
    │ Bank of America      │ Commercial Banks                         │
    ├──────────────────────┼──────────────────────────────────────────┤
    │ Berkshire Hathaway   │ Insurance: Property and Casualty (stock) │
    ├──────────────────────┼──────────────────────────────────────────┤
    │ CVS Health           │ Health Care: Pharmacy and Other Services │
    ├──────────────────────┼──────────────────────────────────────────┤
    │ Cardinal Health      │ Wholesalers: Health Care                 │
    ├──────────────────────┼──────────────────────────────────────────┤
    │ Cencora              │ Wholesalers: Health Care                 │
    ├──────────────────────┼──────────────────────────────────────────┤
    │ Chevron Corporation  │ Petroleum Refining                       │
    ├──────────────────────┼──────────────────────────────────────────┤
    │ Cigna                │ Health Care: Pharmacy and Other Services │
    ├──────────────────────┼──────────────────────────────────────────┤
    │ Costco               │ General Merchandisers                    │
    ├──────────────────────┼──────────────────────────────────────────┤
    │ Elevance Health      │ Health Care: Insurance and Managed Care  │
    ├──────────────────────┼──────────────────────────────────────────┤
    │ ExxonMobil           │ Petroleum Refining                       │
    ├──────────────────────┼──────────────────────────────────────────┤
    │ Ford Motor Company   │ Motor Vehicles & Parts                   │
    ├──────────────────────┼──────────────────────────────────────────┤
    │ General Motors       │ Motor Vehicles & Parts                   │
    ├──────────────────────┼──────────────────────────────────────────┤
    │ JPMorgan Chase       │ Commercial Banks                         │
    ├──────────────────────┼──────────────────────────────────────────┤
    │ McKesson Corporation │ Wholesalers: Health Care                 │
    ├──────────────────────┼──────────────────────────────────────────┤
    │ Microsoft            │ Computer Software                        │
    ├──────────────────────┼──────────────────────────────────────────┤
    │ UnitedHealth Group   │ Health Care: Insurance and Managed Care  │
    ├──────────────────────┼──────────────────────────────────────────┤
    │ Walmart              │ General Merchandisers                    │
    └──────────────────────┴──────────────────────────────────────────┘


Creating a scenario list from a CSV
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The `ScenarioList` method `from_csv('path/to/csv')` can be used to create a list of scenarios from a CSV file.
The method reads the CSV file and creates a scenario for each row in the file, with the keys as the column names and the values as the row values.


Example usage:

Say we have a CSV file with the following data:

.. code-block:: text

    message,user,source,date
    I can't log in...,Alice,Customer support,2022-01-01
    I need help with my bill...,Bob,Phone,2022-01-02
    I have a safety concern...,Charlie,Email,2022-01-03
    I need help with a product...,David,Chat,2022-01-04


We can create a list of scenarios from the CSV file:

.. code-block:: python

    from edsl import ScenarioList

    scenariolist = ScenarioList.from_csv("path/to/csv_file.csv")

    scenariolist


This will return a list consisting of a scenario for each row with the keys as the column names and the values as the row values:

.. code-block:: text

    {
        "scenarios": [
            {
                "message": "I can't log in...",
                "user": "Alice",
                "source": "Customer support",
                "date": "2022-01-01"
            },
            {
                "message": "I need help with my bill...",
                "user": "Bob",
                "source": "Phone",
                "date": "2022-01-02"
            },
            {
                "message": "I have a safety concern...",
                "user": "Charlie",
                "source": "Email",
                "date": "2022-01-03"
            },
            {
                "message": "I need help with a product...",
                "user": "David",
                "source": "Chat",
                "date": "2022-01-04"
            }
        ]
    }


If the scenario keys are not valid Python identifiers, we can use the `give_valid_names()` method to convert them to valid identifiers.

For example, our CSV file might contain a header row that is question texts:

.. code-block:: text

    "What is the message?","Who is the user?","What is the source?","What is the date?"
    "I can't log in...","Alice","Customer support","2022-01-01"
    "I need help with my bill...","Bob","Phone","2022-01-02"
    "I have a safety concern...","Charlie","Email","2022-01-03"
    "I need help with a product...","David","Chat","2022-01-04"


We can create a list of scenarios from the CSV file:

.. code-block:: python

    from edsl import ScenarioList

    scenariolist = ScenarioList.from_csv("path/to/csv_file.csv")

    scenariolist = scenariolist.give_valid_names()

    scenariolist


This will return scenarios with non-Pythonic identifiers:

.. code-block:: text

    {
        "scenarios": [
            {
                "What is the message?": "I can't log in...",
                "Who is the user?": "Alice",
                "What is the source?": "Customer support",
                "What is the date?": "2022-01-01"
            },
            {
                "What is the message?": "I need help with my bill...",
                "Who is the user?": "Bob",
                "What is the source?": "Phone",
                "What is the date?": "2022-01-02"
            },
            {
                "What is the message?": "I have a safety concern...",
                "Who is the user?": "Charlie",
                "What is the source?": "Email",
                "What is the date?": "2022-01-03"
            },
            {
                "What is the message?": "I need help with a product...",
                "Who is the user?": "David",
                "What is the source?": "Chat",
                "What is the date?": "2022-01-04"
            }
        ]
    }


We can then use the `give_valid_names()` method to convert the keys to valid identifiers:

.. code-block:: python

    scenariolist.give_valid_names()

    scenariolist


This will return scenarios with valid identifiers (removing stop words and using underscores):

.. code-block:: text

    {
        "scenarios": [
            {
                "message": "I can't log in...",
                "user": "Alice",
                "source": "Customer support",
                "date": "2022-01-01"
            },
            {
                "message": "I need help with my bill...",
                "user": "Bob",
                "source": "Phone",
                "date": "2022-01-02"
            },
            {
                "message": "I have a safety concern...",
                "user": "Charlie",
                "source": "Email",
                "date": "2022-01-03"
            },
            {
                "message": "I need help with a product...",
                "user": "David",
                "source": "Chat",
                "date": "2022-01-04"
            }
        ]
    }


Methods for un/pivoting and grouping scenarios
----------------------------------------------

There are a variety of methods for modifying scenarios and scenario lists.

Unpivoting a scenario list
^^^^^^^^^^^^^^^^^^^^^^^^^^

The `ScenarioList` method `unpivot()` can be used to unpivot a scenario list based on one or more specified identifiers.
It takes a list of `id_vars` which are the names of the key/value pairs to keep in each new scenario, and a list of `value_vars` which are the names of the key/value pairs to unpivot.

Example usage:

Say we have a scenario list for the above CSV file:

.. code-block:: python

    from edsl import ScenarioList

    scenariolist = ScenarioList.from_csv("path/to/csv_file.csv")

    scenariolist


We can call the unpivot the scenario list:

.. code-block:: python

    scenariolist.unpivot(id_vars = ["user"], value_vars = ["source", "date", "message"])

    scenariolist


This will return a list of scenarios with the `source`, `date`, and `message` key/value pairs unpivoted:

.. code-block:: python

    {
        "scenarios": [
            {
                "user": "Alice",
                "variable": "source",
                "value": "Customer support"
            },
            {
                "user": "Alice",
                "variable": "date",
                "value": "2022-01-01"
            },
            {
                "user": "Alice",
                "variable": "message",
                "value": "I can't log in..."
            },
            {
                "user": "Bob",
                "variable": "source",
                "value": "Phone"
            },
            {
                "user": "Bob",
                "variable": "date",
                "value": "2022-01-02"
            },
            {
                "user": "Bob",
                "variable": "message",
                "value": "I need help with my bill..."
            },
            {
                "user": "Charlie",
                "variable": "source",
                "value": "Email"
            },
            {
                "user": "Charlie",
                "variable": "date",
                "value": "2022-01-03"
            },
            {
                "user": "Charlie",
                "variable": "message",
                "value": "I have a safety concern..."
            },
            {
                "user": "David",
                "variable": "source",
                "value": "Chat"
            },
            {
                "user": "David",
                "variable": "date",
                "value": "2022-01-04"
            },
            {
                "user": "David",
                "variable": "message",
                "value": "I need help with a product..."
            }
        ]
    }


Pivoting a scenario list
^^^^^^^^^^^^^^^^^^^^^^^^

We can call the `pivot()` method to reverse the unpivot operation:

.. code-block:: python

    scenariolist.pivot(id_vars = ["user"], var_name="variable", value_name="value")

    scenariolist


This will return a list of scenarios with the `source`, `date`, and `message` key/value pairs pivoted back to their original form:

.. code-block:: python

    {
        "scenarios": [
            {
                "user": "Alice",
                "source": "Customer support",
                "date": "2022-01-01",
                "message": "I can't log in..."
            },
            {
                "user": "Bob",
                "source": "Phone",
                "date": "2022-01-02",
                "message": "I need help with my bill..."
            },
            {
                "user": "Charlie",
                "source": "Email",
                "date": "2022-01-03",
                "message": "I have a safety concern..."
            },
            {
                "user": "David",
                "source": "Chat",
                "date": "2022-01-04",
                "message": "I need help with a product..."
            }
        ]
    }


Grouping scenarios
^^^^^^^^^^^^^^^^^^

The `group_by()` method can be used to group scenarios by one or more specified keys and apply a function to the values of the specified variables.

Example usage:

.. code-block:: python

    from edsl import ScenarioList

    def avg_sum(a, b):
        return {'avg_a': sum(a) / len(a), 'sum_b': sum(b)}

    scenariolist = ScenarioList([
        Scenario({'group': 'A', 'year': 2020, 'a': 10, 'b': 20}),
        Scenario({'group': 'A', 'year': 2021, 'a': 15, 'b': 25}),
        Scenario({'group': 'B', 'year': 2020, 'a': 12, 'b': 22}),
        Scenario({'group': 'B', 'year': 2021, 'a': 17, 'b': 27})
    ])

    scenariolist.group_by(id_vars=['group'], variables=['a', 'b'], func=avg_sum)


This will return a list of scenarios with the `a` and `b` key/value pairs grouped by the `group` key and the `avg_a` and `sum_b` key/value pairs calculated by the `avg_sum` function:

.. code-block:: python

    {
        "scenarios": [
            {
                "group": "A",
                "avg_a": 12.5,
                "sum_b": 45
            },
            {
                "group": "B",
                "avg_a": 14.5,
                "sum_b": 49
            }
        ]
    }



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
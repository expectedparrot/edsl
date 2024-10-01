.. _scenarios:

Scenarios
=========

A `Scenario` is a dictionary containing a key/value pair that is used to add data or content to questions in a survey, replacing a parameter in a question with a specific value.
A `ScenarioList` is a list of `Scenario` objects.

Purpose 
-------

Scenarios allow you create variations and versions of questions efficiently.
For example, we could create a question `"How much do you enjoy {{ activity }}?"` and use scenarios to replace the parameter `activity` with `running` or `reading` or other activities.
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

    from edsl import QuestionMultipleChoice

    q = QuestionMultipleChoice(
        question_name = "enjoy",
        question_text = "How much do you enjoy {{ activity }}?",
        question_options = ["Not at all", "Somewhat", "Very much"]
    )


Next we create a dictionary for a value that will replace the parameter and store it in a `Scenario` object: 

.. code-block:: python

    from edsl import Scenario 

    scenario = Scenario({"activity": "running"})


We can inspect the scenario and see that it consists of the key/value pair that we created:

.. code-block:: python

    scenario


This will return:

.. code-block:: python

    {
        "activity": "running"
    }


ScenarioList 
^^^^^^^^^^^^

If multiple values will be used, we can create a list of `Scenario` objects:

.. code-block:: python

    scenarios = [Scenario({"activity": a}) for a in ["running", "reading"]]


We can inspect the scenarios:

.. code-block:: python

    scenarios 


This will return:

.. code-block:: python

    [Scenario({'activity': 'running'}), Scenario({'activity': 'reading'})]


We can also create a `ScenarioList` object to store multiple scenarios:

.. code-block:: python

    from edsl import ScenarioList

    scenariolist = ScenarioList([Scenario({"activity": a}) for a in ["running", "reading"]])


We can inspect it:

.. code-block:: python

    scenariolist


This will return:

.. code-block:: python

    {
        "scenarios": [
            {
                "activity": "running"
            },
            {
                "activity": "reading"
            }
        ]
    }


Using a Scenario
----------------

We use a scenario (or scenariolist) by adding it to a question (or a survey of questions), either when constructing the question or else when running it.

We use the `by()` method to add a scenario to a question when running it:

.. code-block:: python

    from edsl import QuestionMultipleChoice, Scenario, Agent

    q = QuestionMultipleChoice(
        question_name = "enjoy",
        question_text = "How much do you enjoy {{ activity }}?",
        question_options = ["Not at all", "Somewhat", "Very much"]
    )

    s = Scenario({"activity": "running"})

    a = Agent(traits = {"persona":"You are a human."})

    results = q.by(s).by(a).run()


We can check the results to verify that the scenario has been used correctly:

.. code-block:: python

    results.select("activity", "enjoy").print(format="rich")


This will print a table of the selected components of the results:

.. code-block:: text

    ┏━━━━━━━━━━━┳━━━━━━━━━━┓
    ┃ scenario  ┃ answer   ┃
    ┃ .activity ┃ .enjoy   ┃
    ┡━━━━━━━━━━━╇━━━━━━━━━━┩
    │ running   │ Somewhat │
    └───────────┴──────────┘


Looping  
-------

We use the `loop()` method to add a scenario to a question when constructing it, passing it a `ScenarioList`. 
This creates a list containing a new question for each scenario that was passed.
Note that we can optionally include the scenario key in the question name as well; otherwise a unique identifies is automatically added to each question name.

For example: 

.. code-block:: python

    from edsl import QuestionMultipleChoice, ScenarioList, Scenario

    q = QuestionMultipleChoice(
        question_name = "enjoy_{{ activity }}",
        question_text = "How much do you enjoy {{ activity }}?",
        question_options = ["Not at all", "Somewhat", "Very much"]
    )

    sl = ScenarioList(
        Scenario({"activity": a}) for a in ["running", "reading"]
    )

    questions = q.loop(sl)


We can inspect the questions to see that they have been created correctly:

.. code-block:: python

    questions


This will return:

.. code-block:: python

    [Question('multiple_choice', question_name = """enjoy_running""", question_text = """How much do you enjoy running?""", question_options = ['Not at all', 'Somewhat', 'Very much']),
    Question('multiple_choice', question_name = """enjoy_reading""", question_text = """How much do you enjoy reading?""", question_options = ['Not at all', 'Somewhat', 'Very much'])]


We can pass the questions to a survey and run it:

.. code-block:: python

    from edsl import Survey, Agent 

    survey = Survey(questions = questions)

    a = Agent(traits = {"persona": "You are a human."})

    results = survey.by(a).run()

    results.select("answer.*").print(format="rich")


This will print a table of the response for each question (note that "activity" is no longer in a separate scenario field):

.. code-block:: text

    ┏━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━┓
    ┃ answer         ┃ answer         ┃
    ┃ .enjoy_reading ┃ .enjoy_running ┃
    ┡━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━┩
    │ Very much      │ Somewhat       │
    └────────────────┴────────────────┘


Multiple parameters
-------------------

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
------------------------------

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

    agents = [Agent({"persona":p}) for p in ["Child", "Magician", "Olympic breakdancer"]]

    results = q_random.by(agents).run()
    results.select("persona", "random").print(format="rich")


Our results are:

.. code-block:: text

    ┏━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
    ┃ agent               ┃ answer  ┃
    ┃ .persona            ┃ .random ┃
    ┡━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
    │ Child               │ 7       │
    ├─────────────────────┼─────────┤
    │ Magician            │ 472     │
    ├─────────────────────┼─────────┤
    │ Olympic breakdancer │ 529     │
    └─────────────────────┴─────────┘


We can use the `to_scenario_list()` method turn components of the results into a list of scenarios to use in a new survey:

.. code-block:: python

    scenarios = results.select("persona", "random").to_scenario_list() # excluding other columns of the results

    scenarios 


We can inspect the scenarios to see that they have been created correctly:

.. code-block:: text

    {
        "scenarios": [
            {
                "persona": "Child",
                "random": 7
            },
            {
                "persona": "Magician",
                "random": 472
            },
            {
                "persona": "Olympic breakdancer",
                "random": 529
            }
        ]
    }


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

The `Scenario` method `from_image('<filepath>.png')` converts a PNG into into a scenario that can be used with an image model (e.g., `gpt-4o`).
This method generates a scenario with a single key - `<filepath>` - that can be used in a question text the same as scenarios from other data sources.

Example usage:

.. code-block:: python

    from edsl import Scenario

    s = Scenario.from_image("logo.png") # Replace with your own local file


Here we use the example scenario, which is the Expected Parrot logo:

.. code-block:: python

    from edsl import Scenario

    s = Scenario.example(has_image = True) 


We can verify the scenario key (the filepath for the image from which the scenario was generated):

.. code-block:: python 

    s.keys()


Output:

.. code-block:: text 

    ['logo']


We can add the key to questions as we do scenarios from other data sources:

.. code-block:: python

    from edsl import Model, QuestionFreeText, QuestionList, Survey

    m = Model("gpt-4o") 
    
    q1 = QuestionFreeText(
        question_name = "identify",
        question_text = "What animal is in this picture: {{ logo }}" # The scenario key is the filepath
    )

    q2 = QuestionList(
        question_name = "colors",
        question_text = "What colors do you see in this picture: {{ logo }}"
    )

    survey = Survey([q1, q2])

    results = survey.by(s).run()

    results.select("logo", "identify", "colors").print(format="rich")


Output using the Expected Parrot logo:

.. code-block:: text 

    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ answer                                                   ┃ answer                                               ┃
    ┃ .identify                                                ┃ .colors                                              ┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ The image shows a large letter "E" followed by a pair of │ ['gray', 'green', 'orange', 'pink', 'blue', 'black'] │
    │ square brackets containing an illustration of a parrot.  │                                                      │
    │ The parrot is green with a yellow beak and some red and  │                                                      │
    │ blue coloring on its body. This combination suggests the │                                                      │
    │ mathematical notation for the expected value, often      │                                                      │
    │ denoted as "E" followed by a random variable in          │                                                      │
    │ brackets, commonly used in probability and statistics.   │                                                      │
    └──────────────────────────────────────────────────────────┴──────────────────────────────────────────────────────┘


See an example of this method in the notebooks section of the docs index: `Using images in a survey <https://docs.expectedparrot.com/en/latest/notebooks/image_scenario_example.html>`_.


Creating a scenario list from a list
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The `ScenarioList` method `from_list()` creates a list of scenarios for a specified key and list of values that is passed to it.

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

The `Scenario` method `from_dict()` creates a scenario for a dictionary that is passed to it.

The `ScenarioList` method `from_nested_dict()` creates a list of scenarios for a specified key and nested dictionary.

Example usage:

.. code-block:: python

    # Example dictionary
    d = {"item": ["color", "food", "animal"]}


    from edsl import Scenario

    scenario = Scenario.from_dict(d)

    scenario


This will return a single scenario for the list of items in the dict:

.. code-block:: text 

    {
        "item": [
            "color",
            "food",
            "animal"
        ]
    }


If we instead want to create a scenario for each item in the list individually:

.. code-block:: python 

    from edsl import ScenarioList

    scenariolist = ScenarioList.from_nested_dict(d)

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

    scenarios = ScenarioList.from_wikipedia("https://en.wikipedia.org/wiki/1990s_in_film", 3)

    scenarios.print(format="rich")


This will return a list of scenarios for the first table on the Wikipedia page:

.. code-block:: text

    ┏━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━┓
    ┃      ┃                                     ┃                                     ┃                 ┃      ┃ Ref ┃
    ┃ Rank ┃ Title                               ┃ Studios                             ┃ Worldwide gross ┃ Year ┃ .   ┃
    ┡━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━┩
    │ 1    │ Titanic                             │ Paramount Pictures/20th Century Fox │ $1,843,201,268  │ 1997 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 2    │ Star Wars: Episode I - The Phantom  │ 20th Century Fox                    │ $924,317,558    │ 1999 │     │
    │      │ Menace                              │                                     │                 │      │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 3    │ Jurassic Park                       │ Universal Pictures                  │ $914,691,118    │ 1993 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 4    │ Independence Day                    │ 20th Century Fox                    │ $817,400,891    │ 1996 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 5    │ The Lion King                       │ Walt Disney Studios                 │ $763,455,561    │ 1994 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 6    │ Forrest Gump                        │ Paramount Pictures                  │ $677,387,716    │ 1994 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 7    │ The Sixth Sense                     │ Walt Disney Studios                 │ $672,806,292    │ 1999 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 8    │ The Lost World: Jurassic Park       │ Universal Pictures                  │ $618,638,999    │ 1997 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 9    │ Men in Black                        │ Sony Pictures/Columbia Pictures     │ $589,390,539    │ 1997 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 10   │ Armageddon                          │ Walt Disney Studios                 │ $553,709,788    │ 1998 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 11   │ Terminator 2: Judgment Day          │ TriStar Pictures                    │ $519,843,345    │ 1991 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 12   │ Ghost                               │ Paramount Pictures                  │ $505,702,588    │ 1990 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 13   │ Aladdin                             │ Walt Disney Studios                 │ $504,050,219    │ 1992 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 14   │ Twister                             │ Warner Bros./Universal Pictures     │ $494,471,524    │ 1996 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 15   │ Toy Story 2                         │ Walt Disney Studios                 │ $485,015,179    │ 1999 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 16   │ Saving Private Ryan                 │ DreamWorks Pictures/Paramount       │ $481,840,909    │ 1998 │     │
    │      │                                     │ Pictures                            │                 │      │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 17   │ Home Alone                          │ 20th Century Fox                    │ $476,684,675    │ 1990 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 18   │ The Matrix                          │ Warner Bros.                        │ $463,517,383    │ 1999 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 19   │ Pretty Woman                        │ Walt Disney Studios                 │ $463,406,268    │ 1990 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 20   │ Mission: Impossible                 │ Paramount Pictures                  │ $457,696,359    │ 1996 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 21   │ Tarzan                              │ Walt Disney Studios                 │ $448,191,819    │ 1999 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 22   │ Mrs. Doubtfire                      │ 20th Century Fox                    │ $441,286,195    │ 1993 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 23   │ Dances with Wolves                  │ Orion Pictures                      │ $424,208,848    │ 1990 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 24   │ The Mummy                           │ Universal Pictures                  │ $415,933,406    │ 1999 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 25   │ The Bodyguard                       │ Warner Bros.                        │ $411,006,740    │ 1992 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 26   │ Robin Hood: Prince of Thieves       │ Warner Bros.                        │ $390,493,908    │ 1991 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 27   │ Godzilla                            │ TriStar Pictures                    │ $379,014,294    │ 1998 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 28   │ True Lies                           │ 20th Century Fox                    │ $378,882,411    │ 1994 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 29   │ Toy Story                           │ Walt Disney Studios                 │ $373,554,033    │ 1995 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 30   │ There's Something About Mary        │ 20th Century Fox                    │ $369,884,651    │ 1998 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 31   │ The Fugitive                        │ Warner Bros.                        │ $368,875,760    │ 1993 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 32   │ Die Hard with a Vengeance           │ 20th Century Fox/Cinergi Pictures   │ $366,101,666    │ 1995 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 33   │ Notting Hill                        │ PolyGram Filmed Entertainment       │ $363,889,678    │ 1999 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 34   │ A Bug's Life                        │ Walt Disney Studios                 │ $363,398,565    │ 1998 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 35   │ The World Is Not Enough             │ Metro-Goldwyn-Mayer Pictures        │ $361,832,400    │ 1999 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 36   │ Home Alone 2: Lost in New York      │ 20th Century Fox                    │ $358,994,850    │ 1992 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 37   │ American Beauty                     │ DreamWorks Pictures                 │ $356,296,601    │ 1999 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 38   │ Apollo 13                           │ Universal Pictures/Imagine          │ $355,237,933    │ 1995 │     │
    │      │                                     │ Entertainment                       │                 │      │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 39   │ Basic Instinct                      │ TriStar Pictures                    │ $352,927,224    │ 1992 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 40   │ GoldenEye                           │ MGM/United Artists                  │ $352,194,034    │ 1995 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 41   │ The Mask                            │ New Line Cinema                     │ $351,583,407    │ 1994 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 42   │ Speed                               │ 20th Century Fox                    │ $350,448,145    │ 1994 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 43   │ Deep Impact                         │ Paramount Pictures/DreamWorks       │ $349,464,664    │ 1998 │     │
    │      │                                     │ Pictures                            │                 │      │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 44   │ Beauty and the Beast                │ Walt Disney Studios                 │ $346,317,207    │ 1991 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 45   │ Pocahontas                          │ Walt Disney Studios                 │ $346,079,773    │ 1995 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 46   │ The Flintstones                     │ Universal Pictures                  │ $341,631,208    │ 1994 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 47   │ Batman Forever                      │ Warner Bros.                        │ $336,529,144    │ 1995 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 48   │ The Rock                            │ Walt Disney Studios                 │ $335,062,621    │ 1996 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 49   │ Tomorrow Never Dies                 │ MGM/United Artists                  │ $333,011,068    │ 1997 │     │
    ├──────┼─────────────────────────────────────┼─────────────────────────────────────┼─────────────────┼──────┼─────┤
    │ 50   │ Seven                               │ New Line Cinema                     │ $327,311,859    │ 1995 │     │
    └──────┴─────────────────────────────────────┴─────────────────────────────────────┴─────────────────┴──────┴─────┘


The `parameters` let us know the keys that can be used in the question text or stored as metadata. 
(They can be edited as needed - e.g., using the `rename` method discussed above.)

.. code-block:: python 

    scenarios.parameters


This will return:

.. code-block:: text

    {'Rank', 'Ref.', 'Studios', 'Title', 'Worldwide gross', 'Year'}


The scenarios can be used to ask questions about the data in the table:

.. code-block:: python

    from edsl import QuestionList

    q_leads = QuestionList(
        question_name = "leads",
        question_text = "Who are the lead actors or actresses in {{ Title }}?"
    )

    results = q_leads.by(scenarios).run()

    (
        results
        .sort_by("Title")
        .select("Title", "leads")
        .print(format="rich")
    )


Output:

.. code-block:: text

    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
    ┃ scenario                                  ┃ answer                                                              ┃
    ┃ .Title                                    ┃ .leads                                                              ┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
    │ A Bug's Life                              │ ['Dave Foley', 'Kevin Spacey', 'Julia Louis-Dreyfus', 'Hayden       │
    │                                           │ Panettiere', 'Phyllis Diller', 'Richard Kind', 'David Hyde Pierce'] │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Aladdin                                   │ ['Mena Massoud', 'Naomi Scott', 'Will Smith']                       │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ American Beauty                           │ ['Kevin Spacey', 'Annette Bening', 'Thora Birch', 'Mena Suvari',    │
    │                                           │ 'Wes Bentley', 'Chris Cooper']                                      │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Apollo 13                                 │ ['Tom Hanks', 'Kevin Bacon', 'Bill Paxton']                         │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Armageddon                                │ ['Bruce Willis', 'Billy Bob Thornton', 'Liv Tyler', 'Ben Affleck']  │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Basic Instinct                            │ ['Michael Douglas', 'Sharon Stone']                                 │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Batman Forever                            │ ['Val Kilmer', 'Tommy Lee Jones', 'Jim Carrey', 'Nicole Kidman',    │
    │                                           │ "Chris O'Donnell"]                                                  │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Beauty and the Beast                      │ ['Emma Watson', 'Dan Stevens', 'Luke Evans', 'Kevin Kline', 'Josh   │
    │                                           │ Gad']                                                               │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Dances with Wolves                        │ ['Kevin Costner', 'Mary McDonnell', 'Graham Greene', 'Rodney A.     │
    │                                           │ Grant']                                                             │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Deep Impact                               │ ['Téa Leoni', 'Morgan Freeman', 'Elijah Wood', 'Robert Duvall']     │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Die Hard with a Vengeance                 │ ['Bruce Willis', 'Samuel L. Jackson', 'Jeremy Irons']               │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Forrest Gump                              │ ['Tom Hanks', 'Robin Wright', 'Gary Sinise', 'Mykelti Williamson',  │
    │                                           │ 'Sally Field']                                                      │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Ghost                                     │ ['Patrick Swayze', 'Demi Moore', 'Whoopi Goldberg']                 │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Godzilla                                  │ ['Matthew Broderick', 'Jean Reno', 'Bryan Cranston', 'Aaron         │
    │                                           │ Taylor-Johnson', 'Elizabeth Olsen', 'Kyle Chandler', 'Vera          │
    │                                           │ Farmiga', 'Millie Bobby Brown']                                     │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ GoldenEye                                 │ ['Pierce Brosnan', 'Sean Bean', 'Izabella Scorupco', 'Famke         │
    │                                           │ Janssen']                                                           │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Home Alone                                │ ['Macaulay Culkin', 'Joe Pesci', 'Daniel Stern', "Catherine         │
    │                                           │ O'Hara", 'John Heard']                                              │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Home Alone 2: Lost in New York            │ ['Macaulay Culkin', 'Joe Pesci', 'Daniel Stern', "Catherine         │
    │                                           │ O'Hara", 'John Heard']                                              │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Independence Day                          │ ['Will Smith', 'Bill Pullman', 'Jeff Goldblum']                     │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Jurassic Park                             │ ['Sam Neill', 'Laura Dern', 'Jeff Goldblum', 'Richard               │
    │                                           │ Attenborough']                                                      │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Men in Black                              │ ['Tommy Lee Jones', 'Will Smith']                                   │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Mission: Impossible                       │ ['Tom Cruise', 'Ving Rhames', 'Simon Pegg', 'Rebecca Ferguson',     │
    │                                           │ 'Jeremy Renner']                                                    │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Mrs. Doubtfire                            │ ['Robin Williams', 'Sally Field', 'Pierce Brosnan', 'Lisa Jakub',   │
    │                                           │ 'Matthew Lawrence', 'Mara Wilson']                                  │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Notting Hill                              │ ['Julia Roberts', 'Hugh Grant']                                     │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Pocahontas                                │ ['Irene Bedard', 'Mel Gibson', 'Judy Kuhn', 'David Ogden Stiers',   │
    │                                           │ 'Russell Means', 'Christian Bale']                                  │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Pretty Woman                              │ ['Richard Gere', 'Julia Roberts']                                   │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Robin Hood: Prince of Thieves             │ ['Kevin Costner', 'Morgan Freeman', 'Mary Elizabeth Mastrantonio',  │
    │                                           │ 'Christian Slater', 'Alan Rickman']                                 │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Saving Private Ryan                       │ ['Tom Hanks', 'Matt Damon', 'Tom Sizemore', 'Edward Burns', 'Barry  │
    │                                           │ Pepper', 'Adam Goldberg', 'Vin Diesel', 'Giovanni Ribisi', 'Jeremy  │
    │                                           │ Davies']                                                            │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Seven                                     │ ['Brad Pitt', 'Morgan Freeman', 'Gwyneth Paltrow']                  │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Speed                                     │ ['Keanu Reeves', 'Sandra Bullock', 'Dennis Hopper']                 │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Star Wars: Episode I - The Phantom Menace │ ['Liam Neeson', 'Ewan McGregor', 'Natalie Portman', 'Jake Lloyd']   │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Tarzan                                    │ ['Johnny Weissmuller', "Maureen O'Sullivan"]                        │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Terminator 2: Judgment Day                │ ['Arnold Schwarzenegger', 'Linda Hamilton', 'Edward Furlong',       │
    │                                           │ 'Robert Patrick']                                                   │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ The Bodyguard                             │ ['Kevin Costner', 'Whitney Houston']                                │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ The Flintstones                           │ ['John Goodman', 'Elizabeth Perkins', 'Rick Moranis', "Rosie        │
    │                                           │ O'Donnell"]                                                         │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ The Fugitive                              │ ['Harrison Ford', 'Tommy Lee Jones']                                │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ The Lion King                             │ ['Matthew Broderick', 'James Earl Jones', 'Jeremy Irons', 'Moira    │
    │                                           │ Kelly', 'Nathan Lane', 'Ernie Sabella', 'Rowan Atkinson', 'Whoopi   │
    │                                           │ Goldberg']                                                          │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ The Lost World: Jurassic Park             │ ['Jeff Goldblum', 'Julianne Moore', 'Pete Postlethwaite']           │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ The Mask                                  │ ['Jim Carrey', 'Cameron Diaz']                                      │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ The Matrix                                │ ['Keanu Reeves', 'Laurence Fishburne', 'Carrie-Anne Moss']          │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ The Mummy                                 │ ['Brendan Fraser', 'Rachel Weisz', 'John Hannah', 'Arnold Vosloo']  │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ The Rock                                  │ ['Sean Connery', 'Nicolas Cage', 'Ed Harris']                       │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ The Sixth Sense                           │ ['Bruce Willis', 'Haley Joel Osment', 'Toni Collette', 'Olivia      │
    │                                           │ Williams']                                                          │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ The World Is Not Enough                   │ ['Pierce Brosnan', 'Sophie Marceau', 'Denise Richards', 'Robert     │
    │                                           │ Carlyle']                                                           │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ There's Something About Mary              │ ['Cameron Diaz', 'Ben Stiller', 'Matt Dillon']                      │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Titanic                                   │ ['Leonardo DiCaprio', 'Kate Winslet']                               │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Tomorrow Never Dies                       │ ['Pierce Brosnan', 'Michelle Yeoh', 'Jonathan Pryce', 'Teri         │
    │                                           │ Hatcher']                                                           │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Toy Story                                 │ ['Tom Hanks', 'Tim Allen']                                          │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Toy Story 2                               │ ['Tom Hanks', 'Tim Allen', 'Joan Cusack']                           │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ True Lies                                 │ ['Arnold Schwarzenegger', 'Jamie Lee Curtis']                       │
    ├───────────────────────────────────────────┼─────────────────────────────────────────────────────────────────────┤
    │ Twister                                   │ ['Helen Hunt', 'Bill Paxton']                                       │
    └───────────────────────────────────────────┴─────────────────────────────────────────────────────────────────────┘


Creating a scenario list from a CSV
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The `ScenarioList` method `from_csv('<filepath>.csv')` creates a list of scenarios from a CSV file.
The method reads the CSV file and creates a scenario for each row in the file, with the keys as the column names and the values as the row values.

For example, say we have a CSV file containing the following data:

.. code-block:: text

    message,user,source,date
    I can't log in...,Alice,Customer support,2022-01-01
    I need help with my bill...,Bob,Phone,2022-01-02
    I have a safety concern...,Charlie,Email,2022-01-03
    I need help with a product...,David,Chat,2022-01-04


We can create a list of scenarios from the CSV file:

.. code-block:: python

    from edsl import ScenarioList

    scenariolist = ScenarioList.from_csv("<filepath>.csv")

    scenariolist


This will return a scenario for each row:

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

    scenariolist = ScenarioList.from_csv("<filepath>.csv")

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

For example, say we have a scenario list for the above CSV file:

.. code-block:: python

    from edsl import ScenarioList

    scenariolist = ScenarioList.from_csv("<filepath>.csv")

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

Scenarios are particularly useful for conducting data labeling or data coding tasks, where the task can be designed as a survey of questions about each piece of data in a dataset.

For example, say we have a dataset of text messages that we want to sort by topic.
We can perform this task by using a language model to answer questions such as `"What is the primary topic of this message: {{ message }}?"` or `"Does this message mention a safety issue? {{ message }}"`, where each text message is inserted in the `message` placeholder of the question text.

Here we use scenarios to conduct the task:

.. code-block:: python

    from edsl import QuestionMultipleChoice, Survey, Scenario

    # Create a question with that takes a parameter
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

    results.select("message", "safety", "topic").print(format="rich")


This will print a table of the scenarios and the answers to the questions for each scenario:

.. code-block:: text

    ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━┓
    ┃ scenario                      ┃ answer  ┃ answer          ┃
    ┃ .message                      ┃ .safety ┃ .topic          ┃
    ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━┩
    │ I can't log in...             │ No      │ Login issue     │
    ├───────────────────────────────┼─────────┼─────────────────┤
    │ I need help with a product... │ No      │ Product support │
    ├───────────────────────────────┼─────────┼─────────────────┤
    │ I need help with my bill...   │ No      │ Billing         │
    ├───────────────────────────────┼─────────┼─────────────────┤
    │ I have a safety concern...    │ Yes     │ Safety          │
    └───────────────────────────────┴─────────┴─────────────────┘


Adding metadata
^^^^^^^^^^^^^^^

If we have metadata about the messages that we want to keep track of, we can add it to the scenarios as well.
This will create additional columns for the metadata in the results dataset, but without the need to include it in our question texts.
Here we modify the above example to use a dataset of messages with metadata. 
Note that the question texts are unchanged:

.. code-block:: python

    from edsl import QuestionMultipleChoice, Survey, ScenarioList, Scenario

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

    scenarios = ScenarioList(
        Scenario.from_dict(m) for m in user_messages
    )

    # Create a survey with the question
    survey = Survey(questions = [q1, q2])

    # Run the survey with the scenarios
    results = survey.by(scenarios).run()

    # Inspect the results
    results.select("scenario.*", "answer.*").print(format="rich")


We can see how the agent answered the questions for each scenario, together with the metadata that was not included in the question text:

.. code-block:: text

    ┏━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━┓
    ┃ scenario ┃ scenario         ┃ scenario                      ┃ scenario   ┃ answer          ┃ answer  ┃
    ┃ .user    ┃ .source          ┃ .message                      ┃ .date      ┃ .topic          ┃ .safety ┃
    ┡━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━┩
    │ Alice    │ Customer support │ I can't log in...             │ 2022-01-01 │ Login issue     │ No      │
    ├──────────┼──────────────────┼───────────────────────────────┼────────────┼─────────────────┼─────────┤
    │ Bob      │ Phone            │ I need help with my bill...   │ 2022-01-02 │ Billing         │ No      │
    ├──────────┼──────────────────┼───────────────────────────────┼────────────┼─────────────────┼─────────┤
    │ Charlie  │ Email            │ I have a safety concern...    │ 2022-01-03 │ Safety          │ Yes     │
    ├──────────┼──────────────────┼───────────────────────────────┼────────────┼─────────────────┼─────────┤
    │ David    │ Chat             │ I need help with a product... │ 2022-01-04 │ Product support │ No      │
    └──────────┴──────────────────┴───────────────────────────────┴────────────┴─────────────────┴─────────┘


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

    word_chunks_scenariolist = text_scenario.chunk(
        "my_text", 
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
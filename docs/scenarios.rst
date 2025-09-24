.. _scenarios:

Scenarios
=========

A `Scenario` is a dictionary containing one or more key/value pairs that is used to add data or content to questions in a survey, replacing a parameter in a question with a specific value (e.g., numerical or textual) or content (e.g., an image or PDF).
A `ScenarioList` is a list of `Scenario` objects.


Purpose 
-------

Scenarios allow you create variations and versions of questions efficiently.
For example, we could create a question `"How much do you enjoy {{ scenario.activity }}?"` and use scenarios to replace the parameter `activity` with `running` or `reading` or other activities.
Similarly, we could create a question `"What do you see in this image? {{ scenario.image }}"` and use scenarios to replace the parameter `image` with different images.


How it works
^^^^^^^^^^^^

Adding scenarios to a question--or to multiple questions at once in a survey--causes it to be administered multiple times, once for each scenario, with the parameter(s) replaced by the value(s) in the scenario.
This allows us to administer different versions of a question together, either asynchronously (by default) or according to `survey rules <https://docs.expectedparrot.com/en/latest/surveys.html#key-methods>`_ that we can specify (e.g., skip/stop logic), without having to create each version of a question manually.


Metadata
^^^^^^^^

Scenarios are also a convenient way to keep track of metadata or other information relating to a survey that is important to an analysis of the results.
For example, say we are using scenarios to parameterize question texts with pieces of `{{ scenario.content }}` from a dataset.
In the scenarios that we create for the `content` parameter we could also include key/value pairs for metadata about the content, such as the `{{ scenario.author }}`, `{{ scenario.publication_date }}`, or `{{ scenario.source }}`.
This will automatically include the data in the survey results but without requiring us to also parameterize the question texts those fields.
This allows us to analyze the responses in the context of the metadata and avoid having to match up the data with the metadata post-survey.
Please see more details on this feature in `examples below <https://docs.expectedparrot.com/en/latest/scenarios.html#adding-metadata>`_.


Constructing a Scenario
-----------------------

To use a scenario, we start by creating a question that takes a parameter in double braces: 

.. code-block:: python

  from edsl import QuestionMultipleChoice

  q = QuestionMultipleChoice(
    question_name = "enjoy",
    question_text = "How much do you enjoy {{ scenario.activity }}?",
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

.. list-table::
  :header-rows: 1

  * - key
    - value 
  * - activity
    - running


ScenarioList 
^^^^^^^^^^^^

If multiple values will be used with a question or survey, we can create a list of `Scenario` objects that will be passed to the question or survey together.
For example, here we create a list of scenarios and inspect them:

.. code-block:: python

  from edsl import Scenario

  scenarios = [Scenario({"activity": a}) for a in ["running", "reading"]]
  scenarios 


Output:

.. code-block:: python

  [Scenario({'activity': 'running'}), Scenario({'activity': 'reading'})]


Alternatively, we can create a `ScenarioList` object.
A list of scenarios is used in the same way as a `ScenarioList`; the difference is that a `ScenarioList` is a class that can be used to create a list of scenarios from a variety of data sources, such as a CSV, dataframe, list, dictionary, a Wikipedia table or a PDF pages.
These special methods are discussed below.

For example, here we create a `ScenarioList` for the same list as above:

.. code-block:: python

  from edsl import Scenario, ScenarioList
    
  scenariolist = ScenarioList(Scenario({"activity": a}) for a in ["running", "reading"])
  scenariolist


Output:

.. list-table::
  :header-rows: 1

  * - activity 
  * - running
  * - reading   


Special method for creating scenarios
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We can use the general purpose `from_source()` method to create a `ScenarioList` from a variety of data source types.
For example, the following code will create the same scenario list as above:

.. code-block:: python
  from edsl import ScenarioList

  scenariolist = ScenarioList.from_source(
    source_type = "list", # or "csv", "dataframe", "delimited_file", "dict", "directory", "dta", "excel", "google_doc", "google_sheet", "json", "latex", "list_of_tuples", "pandas", "parquet", "pdf", "png", "pdf", "pdf_to_image", "text", "tsv", "sqlite", "urls", "wikipedia"
    field_name = "activity", # source-specific positional argument
    values = ["running", "reading"], # source-specific keyword argument
    use_indexes = False # source-specific keyword argument
  )

Each source type has its own set of parameters that can be passed to it:

  * "csv"
  * "dataframe"
  * "delimited_file"
  * "dict"
  * "directory"
  * "dta"
  * "excel"
  * "google_doc"
  * "google_sheet"
  * "json"
  * "latex"
  * "list"
  * "list_of_tuples"
  * "pandas"
  * "parquet"
  * "pdf"
  * "png"
  * "pdf_to_image"
  * "text"
  * "tsv"
  * "sqlite"
  * "urls"
  * "wikipedia"
  

Here we create a scenario list from files in a directory:

.. code-block:: python

  from edsl import ScenarioList, QuestionFreeText
  
  # Create a ScenarioList from all image files in a directory
  # Each file will be wrapped in a Scenario with key "content"
  scenarios = ScenarioList.from_source("directory", "images_folder/*.png")
  
  # Or specify a custom key name (e.g., "image")
  scenarios = ScenarioList.from_source("directory", "images_folder/*.png", "image")
  
  # Create a question that uses the scenario key
  q = QuestionFreeText(
    question_name="image_description",
    question_text="Please describe this image: {{ scenario.image }}"
  )
  
  # Run the question with the scenarios
  results = q.by(scenarios).run()


Examples of these methods are provided below and in `this notebook <https://www.expectedparrot.com/content/RobinHorton/example-scenario-methods>`_.


Using a scenario
----------------

We use a `Scenario` or `ScenarioList` by adding it to a question or survey of questions, either when we are constructing questions or when running them.
If we add scenarios to a question when running a survey (using the `by()` method), the scenario contents replace the parameters in the question text at runtime, and are stored in a separate column of the results.
If we add scenarios to a question when constructing a survey (using the `loop()` method), the scenario contents become part of the question text and there is no separate column of the results for the scenarios.

The most common situation is to add a scenario to a question when running it.
This is done by passing the `Scenario` or `ScenarioList` object to the `by()` method of a question or survey and then chaining the `run()` method.

For example, here we call the `by()` method on the example question created above and pass a scenario list when we run it:

.. code-block:: python

  from edsl import QuestionMultipleChoice, Scenario, ScenarioList, Agent, Model

  q = QuestionMultipleChoice(
    question_name = "enjoy",
    question_text = "How much do you enjoy {{ scenario.activity }}?",
    question_options = ["Not at all", "Somewhat", "Very much"]
  )

  s = ScenarioList(Scenario({"activity":a}) for a in ["running", "sleeping"])

  a = Agent(traits = {"persona":"You are a human."})

  m = Model("gemini-1.5-flash")

  results = q.by(s).by(a).by(m).run()


We can check the results to verify that the scenario has been used correctly:

.. code-block:: python

  results.select("activity", "enjoy")


This will print a table of the selected components of the results:

.. list-table::
  :header-rows: 1

  * - scenario.activity
    - answer.enjoy
  * - running 
    - Somewhat
  * - sleeping
    - Very much


Looping  
^^^^^^^

We use the `loop()` method to add scenarios to a question when constructing a survey.
This method takes a `ScenarioList` and returns a list of new questions for each scenario that was passed.
We can optionally include the scenario key in the question name as well as the question text.
This allows us to control the question names when the new questions are created; otherwise a number is automatically added to the original question name in order to ensure uniqueness.

For example: 

.. code-block:: python

  from edsl import QuestionMultipleChoice, ScenarioList

  q = QuestionMultipleChoice(
    question_name = "enjoy_{{ scenario.activity }}",
    question_text = "How much do you enjoy {{ scenario.activity }}?",
    question_options = ["Not at all", "Somewhat", "Very much"]
  )

  activities = ["running", "reading"]

  sl = ScenarioList.from_list("activity", activities)

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

  results.select("answer.*")


This will print a table of the response for each question.
Note that "activity" is no longer in a separate scenario field; instead, there is a single column for each question that was constructed with the scenarios:

.. list-table::
  :header-rows: 1

  * - answer.enjoy_reading
    - answer.enjoy_running
  * - Very much 
    - Somewhat


*Note:* The `loop()` method *cannot* be used with image or PDF scenarios, as these are not evaluated when the question is constructed.
Instead, use the `by()` method to add these types of scenarios when running a survey (see image scenario examples below).


Multiple parameters
-------------------

We can also create a `Scenario` for multiple parameters at once:

.. code-block:: python

  from edsl import QuestionFreeText, Scenario

  q = QuestionFreeText(
    question_name = "counting",
    question_text = "How many {{ scenario.unit }} are in a {{ scenario.distance }}?",
  )

  scenario = Scenario({"unit": "inches", "distance": "mile"})

  results = q.by(scenario).run()

  results.select("unit", "distance", "counting")


This will print a table of the selected components of the results:

.. list-table::
  :header-rows: 1

  * - scenario.unit
    - scenario.distance
    - answer.counting
  * - inches 
    - mile
    - There are 63,360 inches in a mile.


To learn more about constructing surveys, please see the :ref:`surveys` module.


Scenarios for question options
------------------------------

In the above examples we created scenarios in the `question_text`.
We can also create a `Scenario` for `question_options`, e.g., in a multiple choice, checkbox, linear scale or other question type that requires them.
Note that we do not include the `scenario.` prefix when using sceanrios for question options.

.. code-block:: python

  from edsl import QuestionMultipleChoice, Scenario

  q = QuestionMultipleChoice(
    question_name = "capital_of_france",
    question_text = "What is the capital of France?", 
    question_options = "{{ scenario.question_options }}"
  )

  s = Scenario({'question_options': ['Paris', 'London', 'Berlin', 'Madrid']})

  results = q.by(s).run()

  results.select("answer.*")


Output:

.. list-table::
  :header-rows: 1

  * - answer.capital_of_france
  * - Paris
    

Scenario methods
----------------

There are a variety of methods for working with scenarios and scenario lists, including:
`concatenate`, `concatenate_to_list`, `concatenate_to_set`, `condense`, `drop`, `duplicate` `expand`, `filter`, `keep`, `mutate`, `order_by`, `rename`, `sample`, `shuffle`, `times`, `tranform`, `unpack_dict`

These methods can be used to manipulate scenarios and scenario lists in various ways, such as sampling a subset of scenarios, shuffling the order of scenarios, concatenating scenarios together, filtering scenarios based on certain criteria, and more.
Examples of some of these methods are provided below.


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

.. list-table::
  :header-rows: 1

  * - key
    - value
  * - food 
    - drink 
  * - apple 
    - water


We can also combine `ScenarioList` objects:

.. code-block:: python

  from edsl import Scenario, ScenarioList

  scenariolist1 = ScenarioList([Scenario({"food": "apple"}), Scenario({"drink": "water"})])
  scenariolist2 = ScenarioList([Scenario({"color": "red"}), Scenario({"shape": "circle"})])

  combined_scenariolist = scenariolist1 + scenariolist2

  combined_scenariolist


This will return:

.. list-table::
  :header-rows: 1

  * - food
    - drink
    - color
    - shape
  * - apple 
    - nan
    - nan
    - nan
  * - nan
    - water
    - nan
    - nan
  * - nan
    - nan
    - nan
    - red
  * - nan
    - nan
    - circle
    - nan 


We can create a cross product of `ScenarioList` objects (combine the scenarios in each list with each other):

.. code-block:: python

  from edsl import Scenario, ScenarioList

  scenariolist1 = ScenarioList([Scenario({"food": "apple"}), Scenario({"drink": "water"})])
  scenariolist2 = ScenarioList([Scenario({"color": "red"}), Scenario({"shape": "circle"})])

  cross_product_scenariolist = scenariolist1 * scenariolist2

  cross_product_scenariolist


This will return:

.. list-table::
  :header-rows: 1

  * - food
    - drink
    - color
    - shape
  * - apple 
    - nan
    - nan
    - red
  * - apple
    - nan
    - circle
    - nan
  * - nan
    - water
    - nan
    - red
  * - nan
    - water
    - circle
    - nan


Concatenating scenarios
-----------------------

There are several `ScenarioList` methods for concatenating scenarios.

The method `concatenate()` can be used to concatenate specified fields into a single string field; the default separator is a semicolon:

.. code-block:: python

  from edsl import Scenario, ScenarioList

  sl = ScenarioList([
    Scenario({"a":1, "b":2, "c":3}),
    Scenario({"a":4, "b":5, "c":6})
  ])

  slc = sl.concatenate(["a", "b"])

  slc


This will return:

.. list-table::
  :header-rows: 1

  * - c
    - concat_a_b
  * - 3
    - 1;2
  * - 6
    - 4;5


We can specify a different separator:

.. code-block:: python

  slc = sl.concatenate(["a", "b"], separator = " ")

  slc


This will return:

.. list-table::
  :header-rows: 1

  * - c
    - concat_a_b
  * - 3
    - 1,2
  * - 6
    - 4,5


The method `concatenate_to_list()` can be used to concatenate specified fields into a single list field:

.. code-block:: python

  from edsl import Scenario, ScenarioList

  sl = ScenarioList([
    Scenario({"a":1, "b":2, "c":3}),
    Scenario({"a":4, "b":5, "c":6})
  ])

  slc = sl.concatenate_to_list(["a", "b"])

  slc


This will return:

.. list-table::
  :header-rows: 1

  * - c
    - concat_a_b
  * - 3
    - [1,2]
  * - 6
    - [4,5]


The method `concatenate_to_set()` can be used to concatenate specified fields into a single set field:

.. code-block:: python

  from edsl import Scenario, ScenarioList

  sl = ScenarioList([
    Scenario({"a":1, "b":2, "c":3}),
    Scenario({"a":4, "b":5, "c":6})
  ])

  slc = sl.concatenate_to_list(["a", "b"])

  slc


This will return:

.. list-table::
  :header-rows: 1

  * - c
    - concat_a_b
  * - 3
    - {1,2}
  * - 6
    - {4,5}


The method `collapse()` can be used to collapse a scenario list by grouping on all fields except a specified field:

.. code-block:: python

  from edsl import ScenarioList

  s = ScenarioList([
    Scenario({'category': 'fruit', 'color': 'red', 'item': 'apple'}),
    Scenario({'category': 'fruit', 'color': 'yellow', 'item': 'banana'}),
    Scenario({'category': 'fruit', 'color': 'red', 'item': 'cherry'}),
    Scenario({'category': 'vegetable', 'color': 'green', 'item': 'spinach'})
  ])

  s.collapse('item')


This will return:

.. list-table::
  :header-rows: 1

  * - category
    - color
    - item
  * - fruit
    - red
    - ['apple', 'cherry']
  * - fruit
    - yellow
    - ['banana']
  * - vegetable
    - green
    - ['spinach']
    

The method `condense()` can be used to combine all scenarios in a ScenarioList into a single Scenario object:

.. code-block:: python

  from edsl import Scenario, ScenarioList

  scenarios = ScenarioList([
    Scenario({"id": 1, "text": "First"}),
    Scenario({"id": 2, "text": "Second"}),
    Scenario({"id": 3, "text": "Third"})
  ])

  # Condense with default prefix and index
  combined = scenarios.condense()

  combined


This will return:

.. list-table::
  :header-rows: 1

  * - scenario_0
    - scenario_1
    - scenario_2
  * - {'id': 1, 'text': 'First'}
    - {'id': 2, 'text': 'Second'}
    - {'id': 3, 'text': 'Third'}


The condensed scenario can then be used in EDSL questions with dot notation:

.. code-block:: python

  from edsl import QuestionFreeText

  q = QuestionFreeText(
    question_name="first_text",
    question_text="What is the text from the first scenario: {{ scenario.scenario_0.text }}?"
  )

  # Run with the condensed scenario
  results = q.by(combined).run()


You can also use custom prefixes and control whether to include indices:

.. code-block:: python

  # Custom prefix
  combined_custom = scenarios.condense(prefix="item")

  # Without index (first item uses just prefix, others get index to avoid conflicts)
  combined_no_index = scenarios.condense(prefix="data", include_index=False)

  combined_custom


This will return:

.. list-table::
  :header-rows: 1

  * - item_0
    - item_1
    - item_2
  * - {'id': 1, 'text': 'First'}
    - {'id': 2, 'text': 'Second'}
    - {'id': 3, 'text': 'Third'}


The method `from_source("sqlite")` can be used to create a scenario list from a SQLite database. It takes a `filepath` to the database file and optional parameters `table` and `sql_query`.


Creating scenarios from a dataset
---------------------------------

There are a variety of methods for creating and working with scenarios generated from datasets and different data types.


Turning results into scenarios 
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The method `to_scenario_list()` can be used to turn the results of a survey into a list of scenarios.

Example usage:

Say we have some results from a survey where we asked agents to choose a random number between 1 and 1000:

.. code-block:: python

  from edsl import QuestionNumerical, Agent, AgentList

  q_random = QuestionNumerical(
    question_name = "random",
    question_text = "Choose a random number between 1 and 1000."
  )

  agents = AgentList(Agent({"persona":p}) for p in ["Child", "Magician", "Olympic breakdancer"])

  results = q_random.by(agents).run()

  results.select("persona", "random")


Our results are:

.. list-table::
  :header-rows: 1

  * - agent.persona 
    - answer.random
  * - Child 
    - 7
  * - Magician
    - 472
  * - Olympic breakdancer
    - 529


We can use the `to_scenario_list()` method turn components of the results into a list of scenarios to use in a new survey:

.. code-block:: python

  scenarios = results.select("persona", "random").to_scenario_list() # excluding other columns of the results
  scenarios 


We can inspect the scenarios to see that they have been created correctly:

.. list-table::
  :header-rows: 1

  * - persona 
    - random
  * - Child 
    - 7
  * - Magician
    - 472
  * - Olympic breakdancer
    - 529


PDFs as textual scenarios
^^^^^^^^^^^^^^^^^^^^^^^^^

The `ScenarioList` method `from_source("pdf", "path/to/pdf")` is a convenient way to extract information from large files.
It allows you to read in a PDF and automatically create a list of textual scenarios for the individual pages of the file.
Each scenario has the following keys which can be used as parameters in a question or stored as metadata, and renamed as desired: `filename`, `page`, `text`:

.. code-block:: python

  from edsl import ScenarioList

  scenarios = ScenarioList.from_source("pdf", "path/to/pdf_file.pdf") # modify the filepath


If you prefer to create a single `Scenario` for the entire PDF file, you can use the `FileStore` module to pass the file to a `Scenario` in the usual way (e.g., this method is identical for PNG image files): 

.. code-block:: python

  from edsl import Scenario, FileStore

  fs = FileStore("path/to/pdf") # create a FileStore object for the PDF file (or image file)

  scenario = Scenario({"my_pdf": fs}) # pass the FileStore object to a Scenario


To use this method with either object, we start by adding a placeholder `{{ scenario.text }}` to a question text where the text of a PDF or PDF page will be inserted.
When the question or survey is run with the PDF scenario or scenario list, the text of the PDF or individual pages will be inserted into the question text at the placeholder.

For example, this code can be used to insert the text of each page of a PDF in a survey of question:

.. code-block:: python

  from edsl import QuestionFreeText, ScenarioList, Survey

  # Create a survey of questions parameterized by the {{ text }} of the PDF pages:
  q1 = QuestionFreeText(
    question_name = "themes",
    question_text = "Identify the key themes mentioned on this page: {{ scenario.text }}",
  )

  q2 = QuestionFreeText(
    question_name = "idea",
    question_text = "Identify the most important idea on this page: {{ scenario.text }}",
  )

  survey = Survey([q1, q2])

  scenarios = ScenarioList.from_source("pdf", "path/to/pdf_file.pdf") # modify the filepath

  # Run the survey with the pages of the PDF as scenarios:
  results = survey.by(scenarios).run()

  # To print the page and text of each PDF page scenario together with the answers to the question:
  results.select("page", "text", "answer.*")


Examples of this method can be viewed in a `demo notebook <https://docs.expectedparrot.com/en/latest/notebooks/scenario_from_pdf.html>`_.


Image scenarios
^^^^^^^^^^^^^^^

A `Scenario` can be generated from an image by passing the filepath as the value (the same as a PDF, as shown above).
This is done by using the `FileStore` module to store the image and then passing the `FileStore` object to a `Scenario`.

Example usage:

.. code-block:: python

  from edsl import Scenario, FileStore

  fs = FileStore("parrot_logo.png") # modify filepath 

  s = Scenario({"image":fs}) 


We can add the key to questions as we do scenarios from other data sources:

.. code-block:: python

  from edsl import Model, QuestionFreeText, QuestionList, Survey

  m = Model("gemini-1.5-flash") # we need to use a vision model
  
  q1 = QuestionFreeText(
    question_name = "identify",
    question_text = "What animal is in this picture: {{ scenario.image }}" 
  )

  q2 = QuestionList(
    question_name = "colors",
    question_text = "What colors do you see in this picture: {{ scenario.image }}"
  )

  survey = Survey([q1, q2])

  results = survey.by(s).run()

  results.select("identify", "colors")


Output using the Expected Parrot logo:

.. list-table::
  :header-rows: 1

  * - answer.identify 
    - answer.colors  
  * - The animal in the picture is a parrot.
    - ['gray', 'green', 'yellow', 'pink', 'blue', 'black']


See a `demo notebook <https://docs.expectedparrot.com/en/latest/notebooks/image_scenario_example.html>`_ using of this method in the documentation page.

*Note:* You must use a vision model in order to run questions with images.
We recommend testing whether a model can reliably identify your images before running a survey with them.
You can also use the `models page <https://www.expectedparrot.com/models>`_ to check available models' performance with test questions, including images.


Creating a scenario list from a list
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Example usage:

.. code-block:: python

  from edsl import ScenarioList

  scenariolist = ScenarioList.from_source("list" "item", ["color", "food", "animal"])

  scenariolist


This will return:

.. list-table::
  :header-rows: 1

  * - item 
  * - color
  * - food
  * - animal
    
    
Creating a scenario list from a dictionary
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Example usage:

.. code-block:: python 

  from edsl import ScenarioList

  d = {"item": ["color", "food", "animal"]}

  scenariolist = ScenarioList.from_source("nested_dict", d)
  scenariolist


This will return:

.. list-table::
  :header-rows: 1

  * - item 
  * - color
  * - food
  * - animal


Creating a scenario list from a Wikipedia table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Example usage:

.. code-block:: python

  from edsl import ScenarioList

  scenarios = ScenarioList.from_source("wikipedia", "https://en.wikipedia.org/wiki/1990s_in_film", 3)
  scenarios


This will return a list of scenarios for the first table on the Wikipedia page:

.. list-table:: 
  :header-rows: 1

  * - Rank
    - Title
    - Studios 
    - Worldwide gross
    - Year
  * - 1
    - Titanic
    - Paramount Pictures/20th Century Fox
    - $1,843,201,268
    - 1997
  * - 2
    - Star Wars: Episode I - The Phantom Menace
    - 20th Century Fox
    - $924,317,558
    - 1999
  * - 3
    - Jurassic Park
    - Universal Pictures
    - $914,691,118
    - 1993
  * - 4
    - Independence Day
    - 20th Century Fox
    - $817,400,891
    - 1996
  * - 5
    - The Lion King
    - Walt Disney Studios
    - $763,455,561
    - 1994
  * - 6
    - Forrest Gump
    - Paramount Pictures
    - $677,387,716
    - 1994
  * - 7
    - The Sixth Sense
    - Walt Disney Studios
    - $672,806,292
    - 1999
  * - 8
    - The Lost World: Jurassic Park
    - Universal Pictures
    - $618,638,999
    - 1997
  * - 9
    - Men in Black
    - Sony Pictures/Columbia Pictures
    - $589,390,539
    - 1997
  * - 10
    - Armageddon
    - Walt Disney Studios
    - $553,709,788
    - 1998
  * - 11
    - Terminator 2: Judgment Day
    - TriStar Pictures
    - $519,843,345
    - 1991
  * - 12
    - Ghost
    - Paramount Pictures
    - $505,702,588
    - 1990
  * - 13
    - Aladdin
    - Walt Disney Studios
    - $504,050,219
    - 1992
  * - 14
    - Twister
    - Warner Bros./Universal Pictures
    - $494,471,524
    - 1996
  * - 15
    - Toy Story 2
    - Walt Disney Studios
    - $485,015,179
    - 1999
  * - 16
    - Saving Private Ryan
    - DreamWorks Pictures/Paramount Pictures
    - $481,840,909
    - 1998
  * - 17
    - Home Alone
    - 20th Century Fox
    - $476,684,675
    - 1990
  * - 18
    - The Matrix
    - Warner Bros.
    - $463,517,383
    - 1999
  * - 19
    - Pretty Woman
    - Walt Disney Studios
    - $463,406,268
    - 1990
  * - 20
    - Mission: Impossible
    - Paramount Pictures
    - $457,696,359
    - 1996
  * - 21
    - Tarzan
    - Walt Disney Studios
    - $448,191,819
    - 1999
  * - 22
    - Mrs. Doubtfire
    - 20th Century Fox
    - $441,286,195
    - 1993
  * - 23
    - Dances with Wolves
    - Orion Pictures
    - $424,208,848
    - 1990
  * - 24
    - The Mummy
    - Universal Pictures
    - $415,933,406
    - 1999
  * - 25
    - The Bodyguard
    - Warner Bros.
    - $411,006,740
    - 1992
  * - 26
    - Robin Hood: Prince of Thieves
    - Warner Bros.
    - $390,493,908
    - 1991
  * - 27
    - Godzilla
    - TriStar Pictures
    - $379,014,294
    - 1998
  * - 28
    - True Lies
    - 20th Century Fox
    - $378,882,411
    - 1994
  * - 29
    - Toy Story
    - Walt Disney Studios
    - $373,554,033
    - 1995
  * - 30
    - There's Something About Mary
    - 20th Century Fox
    - $369,884,651
    - 1998
  * - 31
    - The Fugitive
    - Warner Bros.
    - $368,875,760
    - 1993
  * - 32
    - Die Hard with a Vengeance
    - 20th Century Fox/Cinergi Pictures
    - $366,101,666
    - 1995
  * - 33
    - Notting Hill
    - PolyGram Filmed Entertainment
    - $363,889,678
    - 1999
  * - 34
    - A Bug's Life
    - Walt Disney Studios
    - $363,398,565
    - 1998
  * - 35
    - The World Is Not Enough
    - Metro-Goldwyn-Mayer Pictures
    - $361,832,400
    - 1999
  * - 36
    - Home Alone 2: Lost in New York
    - 20th Century Fox
    - $358,994,850
    - 1992
  * - 37
    - American Beauty
    - DreamWorks Pictures
    - $356,296,601
    - 1999
  * - 38
    - Apollo 13
    - Universal Pictures/Imagine Entertainment
    - $355,237,933
    - 1995
  * - 39
    - Basic Instinct
    - TriStar Pictures
    - $352,927,224
    - 1992
  * - 40
    - GoldenEye
    - MGM/United Artists
    - $352,194,034
    - 1995
  * - 41
    - The Mask
    - New Line Cinema
    - $351,583,407
    - 1994
  * - 42
    - Speed
    - 20th Century Fox
    - $350,448,145
    - 1994
  * - 43
    - Deep Impact
    - Paramount Pictures/DreamWorks Pictures
    - $349,464,664
    - 1998
  * - 44
    - Beauty and the Beast
    - Walt Disney Studios
    - $346,317,207
    - 1991
  * - 45
    - Pocahontas
    - Walt Disney Studios
    - $346,079,773
    - 1995
  * - 46
    - The Flintstones
    - Universal Pictures
    - $341,631,208
    - 1994
  * - 47
    - Batman Forever
    - Warner Bros.
    - $336,529,144
    - 1995
  * - 48
    - The Rock
    - Walt Disney Studios
    - $335,062,621
    - 1996
  * - 49
    - Tomorrow Never Dies
    - MGM/United Artists
    - $333,011,068
    - 1997
  * - 50
    - Seven
    - New Line Cinema
    - $327,311,859
    - 1995


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
    question_text = "Who are the lead actors or actresses in {{ scenario.Title }}?"
  )

  results = q_leads.by(scenarios).run()

  (
    results
    .sort_by("Title")
    .select("Title", "leads")
  )


Output:

.. list-table:: 
   :header-rows: 1

   * - Title
     - Leads
   * - A Bug's Life
     - Dave Foley, Kevin Spacey, Julia Louis-Dreyfus, Hayden Panettiere, Phyllis Diller, Richard Kind, David Hyde Pierce
   * - Aladdin
     - Mena Massoud, Naomi Scott, Will Smith
   * - American Beauty
     - Kevin Spacey, Annette Bening, Thora Birch, Mena Suvari, Wes Bentley, Chris Cooper
   * - Apollo 13
     - Tom Hanks, Kevin Bacon, Bill Paxton
   * - Armageddon
     - Bruce Willis, Billy Bob Thornton, Liv Tyler, Ben Affleck
   * - Basic Instinct
     - Michael Douglas, Sharon Stone
   * - Batman Forever
     - Val Kilmer, Tommy Lee Jones, Jim Carrey, Nicole Kidman, Chris O'Donnell
   * - Beauty and the Beast
     - Emma Watson, Dan Stevens, Luke Evans, Kevin Kline, Josh Gad
   * - Dances with Wolves
     - Kevin Costner, Mary McDonnell, Graham Greene, Rodney A. Grant
   * - Deep Impact
     - Téa Leoni, Morgan Freeman, Elijah Wood, Robert Duvall
   * - Die Hard with a Vengeance
     - Bruce Willis, Samuel L. Jackson, Jeremy Irons
   * - Forrest Gump
     - Tom Hanks, Robin Wright, Gary Sinise, Mykelti Williamson, Sally Field
   * - Ghost
     - Patrick Swayze, Demi Moore, Whoopi Goldberg
   * - Godzilla
     - Matthew Broderick, Jean Reno, Bryan Cranston, Aaron Taylor-Johnson, Elizabeth Olsen, Kyle Chandler, Vera Farmiga, Millie Bobby Brown
   * - GoldenEye
     - Pierce Brosnan, Sean Bean, Izabella Scorupco, Famke Janssen
   * - Home Alone
     - Macaulay Culkin, Joe Pesci, Daniel Stern, Catherine O'Hara, John Heard
   * - Home Alone 2: Lost in New York
     - Macaulay Culkin, Joe Pesci, Daniel Stern, Catherine O'Hara, John Heard
   * - Independence Day
     - Will Smith, Bill Pullman, Jeff Goldblum
   * - Jurassic Park
     - Sam Neill, Laura Dern, Jeff Goldblum, Richard Attenborough
   * - Men in Black
     - Tommy Lee Jones, Will Smith
   * - Mission: Impossible
     - Tom Cruise, Ving Rhames, Simon Pegg, Rebecca Ferguson, Jeremy Renner
   * - Mrs. Doubtfire
     - Robin Williams, Sally Field, Pierce Brosnan, Lisa Jakub, Matthew Lawrence, Mara Wilson
   * - Notting Hill
     - Julia Roberts, Hugh Grant
   * - Pocahontas
     - Irene Bedard, Mel Gibson, Judy Kuhn, David Ogden Stiers, Russell Means, Christian Bale
   * - Pretty Woman
     - Richard Gere, Julia Roberts
   * - Robin Hood: Prince of Thieves
     - Kevin Costner, Morgan Freeman, Mary Elizabeth Mastrantonio, Christian Slater, Alan Rickman
   * - Saving Private Ryan
     - Tom Hanks, Matt Damon, Tom Sizemore, Edward Burns, Barry Pepper, Adam Goldberg, Vin Diesel, Giovanni Ribisi, Jeremy Davies
   * - Seven
     - Brad Pitt, Morgan Freeman, Gwyneth Paltrow
   * - Speed
     - Keanu Reeves, Sandra Bullock, Dennis Hopper
   * - Star Wars: Episode I - The Phantom Menace
     - Liam Neeson, Ewan McGregor, Natalie Portman, Jake Lloyd
   * - Tarzan
     - Johnny Weissmuller, Maureen O'Sullivan
   * - Terminator 2: Judgment Day
     - Arnold Schwarzenegger, Linda Hamilton, Edward Furlong, Robert Patrick
   * - The Bodyguard
     - Kevin Costner, Whitney Houston
   * - The Flintstones
     - John Goodman, Elizabeth Perkins, Rick Moranis, Rosie O'Donnell
   * - The Fugitive
     - Harrison Ford, Tommy Lee Jones
   * - The Lion King
     - Matthew Broderick, James Earl Jones, Jeremy Irons, Moira Kelly, Nathan Lane, Ernie Sabella, Rowan Atkinson, Whoopi Goldberg
   * - The Lost World: Jurassic Park
     - Jeff Goldblum, Julianne Moore, Pete Postlethwaite
   * - The Mask
     - Jim Carrey, Cameron Diaz
   * - The Matrix
     - Keanu Reeves, Laurence Fishburne, Carrie-Anne Moss
   * - The Mummy
     - Brendan Fraser, Rachel Weisz, John Hannah, Arnold Vosloo
   * - The Rock
     - Sean Connery, Nicolas Cage, Ed Harris
   * - The Sixth Sense
     - Bruce Willis, Haley Joel Osment, Toni Collette, Olivia Williams
   * - The World Is Not Enough
     - Pierce Brosnan, Sophie Marceau, Denise Richards, Robert Carlyle
   * - There's Something About Mary
     - Cameron Diaz, Ben Stiller, Matt Dillon
   * - Titanic
     - Leonardo DiCaprio, Kate Winslet
   * - Tomorrow Never Dies
     - Pierce Brosnan, Michelle Yeoh, Jonathan Pryce, Teri Hatcher
   * - Toy Story
     - Tom Hanks, Tim Allen
   * - Toy Story 2
     - Tom Hanks, Tim Allen, Joan Cusack
   * - True Lies
     - Arnold Schwarzenegger, Jamie Lee Curtis
   * - Twister
     - Helen Hunt, Bill Paxton


Creating a scenario list from a CSV
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The `ScenarioList` method `from_source("csv", "<filepath>.csv")` creates a list of scenarios from a CSV file.
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

  scenariolist = ScenarioList.from_source("csv", "path/to/file.csv") # update filepath
  scenariolist


This will return a scenario for each row:

.. list-table:: 
   :header-rows: 1

   * - Message
     - User
     - Source
     - Date
   * - I can't log in...
     - Alice
     - Customer support
     - 2022-01-01
   * - I need help with my bill...
     - Bob
     - Phone
     - 2022-01-02
   * - I have a safety concern...
     - Charlie
     - Email
     - 2022-01-03
   * - I need help with a product...
     - David
     - Chat
     - 2022-01-04


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

  scenariolist = ScenarioList.from_source("csv", "path/to/file.csv") # update filepath

  scenariolist = scenariolist.give_valid_names()
  scenariolist


This will return scenarios with non-Pythonic identifiers:

.. list-table::
   :header-rows: 1

   * - What is the message?
     - Who is the user?
     - What is the source?
     - What is the date?
   * - I can't log in...
     - Alice
     - Customer support
     - 2022-01-01
   * - I need help with my bill...
     - Bob
     - Phone
     - 2022-01-02
   * - I have a safety concern...
     - Charlie
     - Email
     - 2022-01-03
   * - I need help with a product...
     - David
     - Chat
     - 2022-01-04


We can then use the `give_valid_names()` method to convert the keys to valid identifiers:

.. code-block:: python

  scenariolist.give_valid_names()
  scenariolist


This will return scenarios with valid identifiers (removing stop words and using underscores):

.. list-table::
   :header-rows: 1

   * - message
     - user
     - source
     - date
   * - I can't log in...
     - Alice
     - Customer support
     - 2022-01-01
   * - I need help with my bill...
     - Bob
     - Phone
     - 2022-01-02
   * - I have a safety concern...
     - Charlie
     - Email
     - 2022-01-03
   * - I need help with a product...
     - David
     - Chat
     - 2022-01-04


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

  scenariolist = ScenarioList.from_source("csv", "<filepath>.csv")
  scenariolist


We can call the unpivot the scenario list:

.. code-block:: python

  scenariolist.unpivot(id_vars = ["user"], value_vars = ["source", "date", "message"])
  scenariolist


This will return a list of scenarios with the `source`, `date`, and `message` key/value pairs unpivoted:

.. list-table::
   :header-rows: 1

   * - user
     - variable
     - value
   * - Alice
     - source
     - Customer support
   * - Alice
     - date
     - 2022-01-01
   * - Alice
     - message
     - I can't log in...
   * - Bob
     - source
     - Phone
   * - Bob
     - date
     - 2022-01-02
   * - Bob
     - message
     - I need help with my bill...
   * - Charlie
     - source
     - Email
   * - Charlie
     - date
     - 2022-01-03
   * - Charlie
     - message
     - I have a safety concern...
   * - David
     - source
     - Chat
   * - David
     - date
     - 2022-01-04
   * - David
     - message
     - I need help with a product...


Pivoting a scenario list
^^^^^^^^^^^^^^^^^^^^^^^^

We can call the `pivot()` method to reverse the unpivot operation:

.. code-block:: python

  scenariolist.pivot(id_vars = ["user"], var_name="variable", value_name="value")
  scenariolist


This will return a list of scenarios with the `source`, `date`, and `message` key/value pairs pivoted back to their original form:

.. list-table::
   :header-rows: 1

   * - user
     - source
     - date
     - message
   * - Alice
     - Customer support
     - 2022-01-01
     - I can't log in...
   * - Bob
     - Phone
     - 2022-01-02
     - I need help with my bill...
   * - Charlie
     - Email
     - 2022-01-03
     - I have a safety concern...
   * - David
     - Chat
     - 2022-01-04
     - I need help with a product...


Grouping scenarios
^^^^^^^^^^^^^^^^^^

The `group_by()` method can be used to group scenarios by one or more specified keys and apply a function to the values of the specified variables.

Example usage:

.. code-block:: python

  from edsl import Scenario, ScenarioList

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

.. list-table::
   :header-rows: 1

   * - group
     - avg_a
     - sum_b
   * - A
     - 12.5
     - 45
   * - B
     - 14.5
     - 49


Data labeling tasks
-------------------

Scenarios are particularly useful for conducting data labeling or data coding tasks, where the task can be designed as a survey of questions about each piece of data in a dataset.

For example, say we have a dataset of text messages that we want to sort by topic.
We can perform this task by using a language model to answer questions such as `"What is the primary topic of this message: {{ scenario.message }}?"` or `"Does this message mention a safety issue? {{ scenario.message }}"`, where each text message is inserted in the `message` placeholder of the question text.

Here we use scenarios to conduct the task:

.. code-block:: python

  from edsl import QuestionMultipleChoice, Survey, Scenario, ScenarioList

  # Create a question with that takes a parameter
  q1 = QuestionMultipleChoice(
    question_name = "topic",
    question_text = "What is the topic of this message: {{ scenario.message }}?",
    question_options = ["Safety", "Product support", "Billing", "Login issue", "Other"]
  )

  q2 = QuestionMultipleChoice(
    question_name = "safety",
    question_text = "Does this message mention a safety issue? {{ scenario.message }}?",
    question_options = ["Yes", "No", "Unclear"]
  )

  # Create a list of scenarios for the parameter
  messages = [
    "I can't log in...", 
    "I need help with my bill...", 
    "I have a safety concern...", 
    "I need help with a product..."
  ]

  scenarios = ScenarioList.from_source("list", "message", messages)

  # Create a survey with the question
  survey = Survey(questions = [q1, q2])

  # Run the survey with the scenarios
  results = survey.by(scenarios).run()


We can then analyze the results to see how the agent answered the questions for each scenario:

.. code-block:: python

  results.select("message", "safety", "topic")


This will print a table of the scenarios and the answers to the questions for each scenario:

.. list-table::
   :header-rows: 1

   * - message
     - safety
     - topic
   * - I can't log in...
     - No
     - Login issue
   * - I need help with a product...
     - No
     - Product support
   * - I need help with my bill...
     - No
     - Billing
   * - I have a safety concern...
     - Yes
     - Safety


Adding metadata
^^^^^^^^^^^^^^^

If we have metadata about the messages that we want to keep track of, we can add it to the scenarios as well.
This will create additional columns for the metadata in the results dataset, but without the need to include it in our question texts.
Here we modify the above example to use a dataset of messages with metadata. 
Note that the question texts are unchanged:

.. code-block:: python

  from edsl import QuestionMultipleChoice, Survey, Scenario, ScenarioList

  # Create a question with a parameter
  q1 = QuestionMultipleChoice(
    question_name = "topic",
    question_text = "What is the topic of this message: {{ scenario.message }}?",
    question_options = ["Safety", "Product support", "Billing", "Login issue", "Other"]
  )

  q2 = QuestionMultipleChoice(
    question_name = "safety",
    question_text = "Does this message mention a safety issue? {{ scenario.message }}?",
    question_options = ["Yes", "No", "Unclear"]
  )

  # Create scenarios for the sets of parameters
  user_messages = [
    {"message": "I can't log in...", "user": "Alice", "source": "Customer support", "date": "2022-01-01"}, 
    {"message": "I need help with my bill...", "user": "Bob", "source": "Phone", "date": "2022-01-02"}, 
    {"message": "I have a safety concern...", "user": "Charlie", "source": "Email", "date": "2022-01-03"}, 
    {"message": "I need help with a product...", "user": "David", "source": "Chat", "date": "2022-01-04"}
  ]

  scenarios = ScenarioList.from_source("dict", user_messages)

  # Create a survey with the question
  survey = Survey(questions = [q1, q2])

  # Run the survey with the scenarios
  results = survey.by(scenarios).run()

  # Inspect the results
  results.select("scenario.*", "answer.*")


We can see how the agent answered the questions for each scenario, together with the metadata that was not included in the question text:

.. list-table::
   :header-rows: 1

   * - user
     - source
     - message
     - date
     - topic
     - safety
   * - Alice
     - Customer support
     - I can't log in...
     - 2022-01-01
     - Login issue
     - No
   * - Bob
     - Phone
     - I need help with my bill...
     - 2022-01-02
     - Billing
     - No
   * - Charlie
     - Email
     - I have a safety concern...
     - 2022-01-03
     - Safety
     - Yes
   * - David
     - Chat
     - I need help with a product...
     - 2022-01-04
     - Product support
     - No


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

.. list-table::
   :header-rows: 1

   * - my_text
     - my_text_chunk
     - my_text_original
   * - This is a long text.
     - 0
     - 4aec42eda32b7f32bde8be6a6bc11125
   * - Pages and pages, oh my!
     - 1
     - 4aec42eda32b7f32bde8be6a6bc11125
   * - I need to chunk it.
     - 2
     - 4aec42eda32b7f32bde8be6a6bc11125


Using f-strings with scenarios
------------------------------

It is possible to use scenarios and f-strings together in a question.
An f-string must be evaluated when a question is constructed, whereas a scenario is either evaluated when a question is run (using the `by` method) or when a question is constructed (using the `loop` method).

For example, here we use an f-string to create different versions of a question that also takes a parameter `{{ scenario.activity }}`, together with a list of scenarios to replace the parameter when the question is run.
We optionally include the f-string in the question name in addition to the question text in order to control the unique identifiers for the questions, which are needed in order to pass the questions that are created to a `Survey`.
(If you do not include the f-string in the question name, a number is automatically appended to each question name to ensure uniqueness.)
Then we use the `show_prompts()` method to examine the user prompts that are created when the scenarios are added to the questions:

.. code-block:: python

  from edsl import QuestionFreeText, Scenario, ScenarioList, Survey

  questions = []
  sentiments = ["enjoy", "hate", "love"]
  activities = ["running", "reading"]

  for sentiment in sentiments:
    q = QuestionFreeText(
      question_name = f"{ sentiment }_activity",
      question_text = f"How much do you { sentiment } " + "{{ scenario.activity }}?"
    )
    questions.append(q)

  scenarios = ScenarioList.from_source("list", "activity", activities)

  survey = Survey(questions = questions)
  survey.by(scenarios).show_prompts()


The `show_prompts` method will return the questions created with the f-string with the scenarios added.
(Note that the system prompts are blank because we have not created any agents.)

.. list-table::
  :header-rows: 1

  * - user_prompt
    - system_prompt
  * - How much do you enjoy running?
    - 
  * - How much do you hate running?
    - 
  * - How much do you love running?
    - 
  * - How much do you enjoy reading?
    - 
  * - How much do you hate reading?
    - 
  * - How much do you love reading? 
    - 
    

To learn more about user and system prompts, please see the :ref:`prompts` section.


Special methods
---------------

Special methods are available for generating or modifying scenarios using web searches:

The `from_prompt` method allows you to create scenarios from a prompt, which can be useful for generating scenarios based on user input or other dynamic sources:

.. code-block:: python

  from edsl import ScenarioList

  scenarios = ScenarioList.from_prompt(
    description = "What are some popular programming languages?",
    name = "programming_languages", # optional name for the scenarios; default is "item"
    target_number = 5, # optional number of scenarios to generate; default is 10
    verbose = True # optional flag to return verbose output; default is False
  )
  

The `from_search_terms` method allows you to create scenarios from a list of search terms, which can be useful for generating scenarios based on search queries or other dynamic sources:

.. code-block:: python

  from edsl import ScenarioList

  search_terms = ["Python", "Java", "JavaScript"]
  scenarios = ScenarioList.from_search_terms(search_terms)


The method `augment_with_wikipedia` allows you to augment scenarios with information from Wikipedia, which can be useful for enriching scenarios with additional context or data:

.. code-block:: python

  from edsl import ScenarioList

  # method is used to augment existing scenarios
  scenarios = ScenarioList.from_prompt(
    description = "What are some popular programming languages?",
    name = "programming_languages"
  )
  
  scenarios.augment_with_wikipedia(
    search_key = "programming languages",
    content_only = True # default optional flag to return only the content
    key_name = "wikipedia_content" # default optional key name for the content
  )



Scenario class
--------------

.. autoclass:: edsl.scenarios.Scenario
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__ 


ScenarioList class
------------------

.. autoclass:: edsl.scenarios.ScenarioList
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__ 
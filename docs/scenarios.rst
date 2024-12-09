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
This allows us to administer multiple versions of the question together in a survey, either asynchronously (by default) or according to :ref:`surveys` rules that we can specify (e.g., skip/stop logic), without having to create each question manually.


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

.. list-table::
  :header-rows: 1

  * - key
    - activity 
  * - value
    - running


ScenarioList 
^^^^^^^^^^^^

If multiple values will be used, we can create a list of `Scenario` objects:

.. code-block:: python

    from edsl import Scenario

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

.. list-table::
  :header-rows: 1

  * - activity 
    - running
    - reading   


A list of scenarios is used in the same way as a `ScenarioList`.
The difference is that a `ScenarioList` is a class that can be used to create a list of scenarios from a variety of data sources, such as a list, dictionary, or a Wikipedia table (see examples below).


Using f-strings with scenarios
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is possible to use scenarios and f-strings together in a question.
An f-string must be evaluated when a question is constructed, whereas a scenario is evaluated when a question is run.

For example, here we use an f-string to create different versions of a question that also takes a parameter `{{ activity }}`, together with a list of scenarios to replace the parameter when the questions are run.
We optionally include the f-string in the question name as well as the question text in order to simultaneously create unique identifiers for the questions, which are needed in order to pass the questions that are created to a `Survey`.
Then we use the `show_prompts()` method to examine the user prompts that are created when the scenarios are added to the questions:

.. code-block:: python

    from edsl import QuestionFreeText, ScenarioList, Scenario, Survey

    questions = []
    sentiments = ["enjoy", "hate", "love"]

    for sentiment in sentiments:
        q = QuestionFreeText(
            question_name = f"{ sentiment }_activity",
            question_text = f"How much do you { sentiment } {{ activity }}?"
        )
        questions.append(q)

    scenarios = ScenarioList(
        Scenario({"activity": activity}) for activity in ["running", "reading"]
    )

    survey = Survey(questions = questions)
    survey.by(scenarios).show_prompts()


This will print the questions created with the f-string with the scenarios added (not that the system prompts are blank because we have not created any agents):

.. list-table::
  :header-rows: 1

  * - user_prompt
    - How much do you enjoy running?
    - How much do you hate running?
    - How much do you love running?
    - How much do you enjoy reading?
    - How much do you hate reading?
    - How much do you love reading? 
  * - system_prompt
    - 
    -
    -
    -
    -
    -
    

To learn more about prompts, please see the :ref:`prompts` section.


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

    results.select("activity", "enjoy")


This will print a table of the selected components of the results:

.. list-table::
  :header-rows: 1

  * - scenario.activity
    - running 
  * - answer.enjoy
    - Somewhat


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

    results.select("answer.*")


This will print a table of the response for each question (note that "activity" is no longer in a separate scenario field):

.. list-table::
  :header-rows: 1

  * - answer.enjoy_reading
    - Very much 
  * - answer.enjoy_running
    - Somewhat


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

    results.select("unit", "distance", "counting")


This will print a table of the selected components of the results:

.. list-table::
  :header-rows: 1

  * - scenario.unit
    - inches 
  * - scenario.distance
    - mile
  * - answer.counting
    - There are 63,360 inches in a mile.


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

    results.select("answer.*")


Output:

.. list-table::
  :header-rows: 1

  * - answer.capital_of_france
    - Paris
    

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
    - food 
    - drink 
  * - value
    - apple 
    - water


We can also combine `ScenarioList` objects:

.. code-block:: python

    from edsl import ScenarioList

    scenariolist1 = ScenarioList([Scenario({"food": "apple"}), Scenario({"drink": "water"})])
    scenariolist2 = ScenarioList([Scenario({"color": "red"}), Scenario({"shape": "circle"})])

    combined_scenariolist = scenariolist1 + scenariolist2

    combined_scenariolist


This will return:

.. list-table::
  :header-rows: 1

  * - food
    - apple 
    - 
    - 
    -
  * - drink 
    - 
    - water
    -
    -
  * - color 
    - 
    - 
    - red
    -
  * - shape 
    - 
    -
    -
    - circle 


We can create a cross product of `ScenarioList` objects (combine the scenarios in each list with each other):

.. code-block:: python

    from edsl import ScenarioList

    scenariolist1 = ScenarioList([Scenario({"food": "apple"}), Scenario({"drink": "water"})])
    scenariolist2 = ScenarioList([Scenario({"color": "red"}), Scenario({"shape": "circle"})])

    cross_product_scenariolist = scenariolist1 * scenariolist2

    cross_product_scenariolist


This will return:

.. list-table::
  :header-rows: 1

  * - food
    - apple 
    - apple
    - 
    -
  * - drink
    - 
    - 
    - water
    - water
  * - color
    - red
    - 
    - red
    -
  * - shape
    -
    - circle
    - 
    - circle


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
    results.select("persona", "random")


Our results are:

.. list-table::
  :header-rows: 1

  * - agent.persona 
    - Child 
    - Magician
    - Olympic breakdancer
  * - answer.random
    - 7
    - 472
    - 529


We can use the `to_scenario_list()` method turn components of the results into a list of scenarios to use in a new survey:

.. code-block:: python

    scenarios = results.select("persona", "random").to_scenario_list() # excluding other columns of the results

    scenarios 


We can inspect the scenarios to see that they have been created correctly:

.. list-table::
  :header-rows: 1

  * - persona 
    - Child 
    - Magician
    - Olympic breakdancer
  * - random
    - 7 
    - 472
    - 529


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
    results.select("page", "text", "answer.*")


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

    results.select("logo", "identify", "colors")


Output using the Expected Parrot logo:

.. list-table::
  :header-rows: 1

  * - answer.identify 
    - The image shows a large letter "E" followed by a pair of square brackets containing an illustration of a parrot. The parrot is green with a yellow beak and some red and blue coloring on its body. This combination suggests the mathematical notation for the expected value, often denoted as "E" followed by a random variable in brackets, commonly used in probability and statistics.
  * - answer.colors  
    - ['gray', 'green', 'orange', 'pink', 'blue', 'black']


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

.. list-table::
  :header-rows: 1

  * - item 
    - color
    - food
    - animal
    
    
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

.. list-table::
  :header-rows: 1

  * - key
    - item:0
    - item:1
    - item:2 
  * - value  
    - color
    - food
    - animal


If we instead want to create a scenario for each item in the list individually:

.. code-block:: python 

    from edsl import ScenarioList

    scenariolist = ScenarioList.from_nested_dict(d)

    scenariolist


This will return:

.. list-table::
  :header-rows: 1

  * - item 
    - color
    - food
    - animal


Creating a scenario list from a Wikipedia table
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The `ScenarioList` method `from_wikipedia_table('url')` can be used to create a list of scenarios from a Wikipedia table.

Example usage:

.. code-block:: python

    from edsl import ScenarioList

    scenarios = ScenarioList.from_wikipedia("https://en.wikipedia.org/wiki/1990s_in_film", 3)

    scenarios


This will return a list of scenarios for the first table on the Wikipedia page:

.. list-table:: 
  :header-rows: 1

  * - Rank
    - 1
    - 2
    - 3
    - 4
    - 5
    - 6
    - 7
    - 8
    - 9
    - 10
    - 11
    - 12
    - 13
    - 14
    - 15
    - 16
    - 17
    - 18
    - 19
    - 20
    - 21
    - 22
    - 23
    - 24
    - 25
    - 26
    - 27
    - 28
    - 29
    - 30
    - 31
    - 32
    - 33
    - 34
    - 35
    - 36
    - 37
    - 38
    - 39
    - 40
    - 41
    - 42
    - 43
    - 44
    - 45
    - 46
    - 47
    - 48
    - 49
    - 50
  * - Title
    - Titanic
    - Star Wars: Episode I - The Phantom Menace
    - Jurassic Park
    - Independence Day
    - The Lion King
    - Forrest Gump
    - The Sixth Sense
    - The Lost World: Jurassic Park
    - Men in Black
    - Armageddon
    - Terminator 2: Judgment Day
    - Ghost
    - Aladdin
    - Twister
    - Toy Story 2
    - Saving Private Ryan
    - Home Alone
    - The Matrix
    - Pretty Woman
    - Mission: Impossible
    - Tarzan
    - Mrs. Doubtfire
    - Dances with Wolves
    - The Mummy
    - The Bodyguard
    - Robin Hood: Prince of Thieves
    - Godzilla
    - True Lies
    - Toy Story
    - There's Something About Mary
    - The Fugitive
    - Die Hard with a Vengeance
    - Notting Hill
    - A Bug's Life
    - The World Is Not Enough
    - Home Alone 2: Lost in New York
    - American Beauty
    - Apollo 13
    - Basic Instinct
    - GoldenEye
    - The Mask
    - Speed
    - Deep Impact
    - Beauty and the Beast
    - Pocahontas
    - The Flintstones
    - Batman Forever
    - The Rock
    - Tomorrow Never Dies
    - Seven
  * - Studios
    - Paramount Pictures/20th Century Fox
    - 20th Century Fox
    - Universal Pictures
    - 20th Century Fox
    - Walt Disney Studios
    - Paramount Pictures
    - Walt Disney Studios
    - Universal Pictures
    - Sony Pictures/Columbia Pictures
    - Walt Disney Studios
    - TriStar Pictures
    - Paramount Pictures
    - Walt Disney Studios
    - Warner Bros./Universal Pictures
    - Walt Disney Studios
    - DreamWorks Pictures/Paramount Pictures
    - 20th Century Fox
    - Warner Bros.
    - Walt Disney Studios
    - Paramount Pictures
    - Walt Disney Studios
    - 20th Century Fox
    - Orion Pictures
    - Universal Pictures
    - Warner Bros.
    - Warner Bros.
    - TriStar Pictures
    - 20th Century Fox
    - Walt Disney Studios
    - 20th Century Fox
    - Warner Bros.
    - 20th Century Fox/Cinergi Pictures
    - PolyGram Filmed Entertainment
    - Walt Disney Studios
    - Metro-Goldwyn-Mayer Pictures
    - 20th Century Fox
    - DreamWorks Pictures
    - Universal Pictures/Imagine Entertainment
    - TriStar Pictures
    - MGM/United Artists
    - New Line Cinema
    - 20th Century Fox
    - Paramount Pictures/DreamWorks Pictures
    - Walt Disney Studios
    - Walt Disney Studios
    - Universal Pictures
    - Warner Bros.
    - Walt Disney Studios
    - MGM/United Artists
    - New Line Cinema
  * - Worldwide gross
    - $1,843,201,268
    - $924,317,558
    - $914,691,118
    - $817,400,891
    - $763,455,561
    - $677,387,716
    - $672,806,292
    - $618,638,999
    - $589,390,539
    - $553,709,788
    - $519,843,345
    - $505,702,588
    - $504,050,219
    - $494,471,524
    - $485,015,179
    - $481,840,909
    - $476,684,675
    - $463,517,383
    - $463,406,268
    - $457,696,359
    - $448,191,819
    - $441,286,195
    - $424,208,848
    - $415,933,406
    - $411,006,740
    - $390,493,908
    - $379,014,294
    - $378,882,411
    - $373,554,033
    - $369,884,651
    - $368,875,760
    - $366,101,666
    - $363,889,678
    - $363,398,565
    - $361,832,400
    - $358,994,850
    - $356,296,601
    - $355,237,933
    - $352,927,224
    - $352,194,034
    - $351,583,407
    - $350,448,145
    - $349,464,664
    - $346,317,207
    - $346,079,773
    - $341,631,208
    - $336,529,144
    - $335,062,621
    - $333,011,068
    - $327,311,859
  * - Year
    - 1997
    - 1999
    - 1993
    - 1996
    - 1994
    - 1994
    - 1999
    - 1997
    - 1997
    - 1998
    - 1991
    - 1990
    - 1992
    - 1996
    - 1999
    - 1998
    - 1990
    - 1999
    - 1990
    - 1996
    - 1999
    - 1993
    - 1990
    - 1999
    - 1992
    - 1991
    - 1998
    - 1994
    - 1995
    - 1998
    - 1993
    - 1995
    - 1999
    - 1998
    - 1999
    - 1992
    - 1999
    - 1995
    - 1992
    - 1995
    - 1994
    - 1994
    - 1998
    - 1991
    - 1995
    - 1994
    - 1995
    - 1996
    - 1997
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
        question_text = "Who are the lead actors or actresses in {{ Title }}?"
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
    - A Bug's Life
    - Aladdin
    - American Beauty
    - Apollo 13
    - Armageddon
    - Basic Instinct
    - Batman Forever
    - Beauty and the Beast
    - Dances with Wolves
    - Deep Impact
    - Die Hard with a Vengeance
    - Forrest Gump
    - Ghost
    - Godzilla
    - GoldenEye
    - Home Alone
    - Home Alone 2: Lost in New York
    - Independence Day
    - Jurassic Park
    - Men in Black
    - Mission: Impossible
    - Mrs. Doubtfire
    - Notting Hill
    - Pocahontas
    - Pretty Woman
    - Robin Hood: Prince of Thieves
    - Saving Private Ryan
    - Seven
    - Speed
    - Star Wars: Episode I - The Phantom Menace
    - Tarzan
    - Terminator 2: Judgment Day
    - The Bodyguard
    - The Flintstones
    - The Fugitive
    - The Lion King
    - The Lost World: Jurassic Park
    - The Mask
    - The Matrix
    - The Mummy
    - The Rock
    - The Sixth Sense
    - The World Is Not Enough
    - There's Something About Mary
    - Titanic
    - Tomorrow Never Dies
    - Toy Story
    - Toy Story 2
    - True Lies
    - Twister
  * - Leads
    - Dave Foley, Kevin Spacey, Julia Louis-Dreyfus, Hayden Panettiere, Phyllis Diller, Richard Kind, David Hyde Pierce
    - Mena Massoud, Naomi Scott, Will Smith
    - Kevin Spacey, Annette Bening, Thora Birch, Mena Suvari, Wes Bentley, Chris Cooper
    - Tom Hanks, Kevin Bacon, Bill Paxton
    - Bruce Willis, Billy Bob Thornton, Liv Tyler, Ben Affleck
    - Michael Douglas, Sharon Stone
    - Val Kilmer, Tommy Lee Jones, Jim Carrey, Nicole Kidman, Chris O'Donnell
    - Emma Watson, Dan Stevens, Luke Evans, Kevin Kline, Josh Gad
    - Kevin Costner, Mary McDonnell, Graham Greene, Rodney A. Grant
    - Téa Leoni, Morgan Freeman, Elijah Wood, Robert Duvall
    - Bruce Willis, Samuel L. Jackson, Jeremy Irons
    - Tom Hanks, Robin Wright, Gary Sinise, Mykelti Williamson, Sally Field
    - Patrick Swayze, Demi Moore, Whoopi Goldberg
    - Matthew Broderick, Jean Reno, Bryan Cranston, Aaron Taylor-Johnson, Elizabeth Olsen, Kyle Chandler, Vera Farmiga, Millie Bobby Brown
    - Pierce Brosnan, Sean Bean, Izabella Scorupco, Famke Janssen
    - Macaulay Culkin, Joe Pesci, Daniel Stern, Catherine O'Hara, John Heard
    - Macaulay Culkin, Joe Pesci, Daniel Stern, Catherine O'Hara, John Heard
    - Will Smith, Bill Pullman, Jeff Goldblum
    - Sam Neill, Laura Dern, Jeff Goldblum, Richard Attenborough
    - Tommy Lee Jones, Will Smith
    - Tom Cruise, Ving Rhames, Simon Pegg, Rebecca Ferguson, Jeremy Renner
    - Robin Williams, Sally Field, Pierce Brosnan, Lisa Jakub, Matthew Lawrence, Mara Wilson
    - Julia Roberts, Hugh Grant
    - Irene Bedard, Mel Gibson, Judy Kuhn, David Ogden Stiers, Russell Means, Christian Bale
    - Richard Gere, Julia Roberts
    - Kevin Costner, Morgan Freeman, Mary Elizabeth Mastrantonio, Christian Slater, Alan Rickman
    - Tom Hanks, Matt Damon, Tom Sizemore, Edward Burns, Barry Pepper, Adam Goldberg, Vin Diesel, Giovanni Ribisi, Jeremy Davies
    - Brad Pitt, Morgan Freeman, Gwyneth Paltrow
    - Keanu Reeves, Sandra Bullock, Dennis Hopper
    - Liam Neeson, Ewan McGregor, Natalie Portman, Jake Lloyd
    - Johnny Weissmuller, Maureen O'Sullivan
    - Arnold Schwarzenegger, Linda Hamilton, Edward Furlong, Robert Patrick
    - Kevin Costner, Whitney Houston
    - John Goodman, Elizabeth Perkins, Rick Moranis, Rosie O'Donnell
    - Harrison Ford, Tommy Lee Jones
    - Matthew Broderick, James Earl Jones, Jeremy Irons, Moira Kelly, Nathan Lane, Ernie Sabella, Rowan Atkinson, Whoopi Goldberg
    - Jeff Goldblum, Julianne Moore, Pete Postlethwaite
    - Jim Carrey, Cameron Diaz
    - Keanu Reeves, Laurence Fishburne, Carrie-Anne Moss
    - Brendan Fraser, Rachel Weisz, John Hannah, Arnold Vosloo
    - Sean Connery, Nicolas Cage, Ed Harris
    - Bruce Willis, Haley Joel Osment, Toni Collette, Olivia Williams
    - Pierce Brosnan, Sophie Marceau, Denise Richards, Robert Carlyle
    - Cameron Diaz, Ben Stiller, Matt Dillon
    - Leonardo DiCaprio, Kate Winslet
    - Pierce Brosnan, Michelle Yeoh, Jonathan Pryce, Teri Hatcher
    - Tom Hanks, Tim Allen
    - Tom Hanks, Tim Allen, Joan Cusack
    - Arnold Schwarzenegger, Jamie Lee Curtis
    - Helen Hunt, Bill Paxton


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

.. list-table:: 
  :header-rows: 1

  * - Message
    - I can't log in...
    - I need help with my bill...
    - I have a safety concern...
    - I need help with a product...
  * - User
    - Alice
    - Bob
    - Charlie  
    - David
  * - Source
    - Customer support
    - Phone
    - Email
    - Chat
  * - Date
    - 2022-01-01
    - 2022-01-02
    - 2022-01-03
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

    scenariolist = ScenarioList.from_csv("<filepath>.csv")

    scenariolist = scenariolist.give_valid_names()

    scenariolist


This will return scenarios with non-Pythonic identifiers:

.. list-table::
  :header-rows: 1

  * - What is the message?
    - I can't log in...
    - I need help with my bill...
    - I have a safety concern...
    - I need help with a product...
  * - Who is the user?
    - Alice
    - Bob
    - Charlie
    - David
  * - What is the source?
    - Customer support
    - Phone
    - Email
    - Chat
  * - What is the date?
    - 2022-01-01
    - 2022-01-02
    - 2022-01-03
    - 2022-01-04


We can then use the `give_valid_names()` method to convert the keys to valid identifiers:

.. code-block:: python

    scenariolist.give_valid_names()

    scenariolist


This will return scenarios with valid identifiers (removing stop words and using underscores):

.. list-table::
  :header-rows: 1

  * - message
    - I can't log in...
    - I need help with my bill...
    - I have a safety concern...
    - I need help with a product...
  * - user
    - Alice
    - Bob
    - Charlie
    - David
  * - source
    - Customer support
    - Phone
    - Email
    - Chat
  * - date
    - 2022-01-01 
    - 2022-01-02
    - 2022-01-03
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

    scenariolist = ScenarioList.from_csv("<filepath>.csv")

    scenariolist


We can call the unpivot the scenario list:

.. code-block:: python

    scenariolist.unpivot(id_vars = ["user"], value_vars = ["source", "date", "message"])

    scenariolist


This will return a list of scenarios with the `source`, `date`, and `message` key/value pairs unpivoted:

.. list-table::
  :header-rows: 1

  * - user
    - Alice
    - Alice
    - Alice 
    - Bob
    - Bob
    - Bob
    - Charlie
    - Charlie
    - Charlie
    - David
    - David
    - David
  * - variable
    - source
    - date
    - message
    - source
    - date 
    - message
    - source
    - date
    - message
    - source
    - date
    - message
  * - value
    - Customer support
    - 2022-01-01
    - I can't log in...
    - Phone
    - 2022-01-02 
    - I need help with my bill...
    - Email
    - 2022-01-03
    - I have a safety concern...
    - Chat
    - 2022-01-04
    - I need help with a product...


Pivoting a scenario list
^^^^^^^^^^^^^^^^^^^^^^^^

We can call the `pivot()` method to reverse the unpivot operation:

.. code-block:: python

    scenariolist.pivot(id_vars = ["user"], var_name="variable", value_name="value")

    scenariolist


This will return a list of scenarios with the `source`, `date`, and `message` key/value pairs pivoted back to their original form:

.. code-block:: python

.. list-table::
  :header-rows: 1

  * - user
    - Alice
    - Bob
    - Charlie
    - David
  * - source
    - Customer support
    - Phone
    - Email
    - Chat
  * - date
    - 2022-01-01
    - 2022-01-02
    - 2022-01-03
    - 2022-01-04
  * - message
    - I can't log in...
    - I need help with my bill...
    - I have a safety concern...
    - I need help with a product...


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

.. list-table::
  :header-rows: 1

  * - group
    - A
    - B
  * - avg_a
    - 12.5
    - 14.5
  * - sum_b
    - 45
    - 49


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

    results.select("message", "safety", "topic")


This will print a table of the scenarios and the answers to the questions for each scenario:

.. list-table::
  :header-rows: 1

  * - message
    - I can't log in...
    - I need help with a product...
    - I need help with my bill...
    - I have a safety concern...
  * - safety
    - No
    - No
    - No
    - Yes
  * - topic
    - Login issue
    - Product support
    - Billing
    - Safety


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
    results.select("scenario.*", "answer.*")


We can see how the agent answered the questions for each scenario, together with the metadata that was not included in the question text:

.. list-table::
  :header-rows: 1

  * - user
    - Alice
    - Bob
    - Charlie
    - David
  * - source
    - Customer support
    - Phone
    - Email
    - Chat
  * - message
    - I can't log in...
    - I need help with my bill...
    - I have a safety concern...
    - I need help with a product...
  * - date
    - 2022-01-01
    - 2022-01-02
    - 2022-01-03
    - 2022-01-04
  * - topic
    - Login issue
    - Billing
    - Safety 
    - Product support
  * - safety
    - No
    - No
    - Yes
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
    - This is a long text.
    - Pages and pages, oh my!
    - I need to chunk it.
  * - my_text_chunk
    - 0
    - 1
    - 2
  * - my_text_original
    - 4aec42eda32b7f32bde8be6a6bc11125
    - 4aec42eda32b7f32bde8be6a6bc11125
    - 4aec42eda32b7f32bde8be6a6bc11125



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
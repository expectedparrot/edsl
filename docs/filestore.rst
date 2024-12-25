.. _filestore:

File Store
==========

`FileStore` is a module for storing and sharing data files at Coop.
It allows you to post and retrieve files of various types to use in EDSL surveys, such as survey data, PDFs, CSVs, docs or images.
It can also be used to create `Scenario` objects for questions or traits for `Agent` objects from data files at Coop.
When posting files, the `FileStore` module will automatically infer the file type from the extension.

*Note:* Scenarios created from `FileStore` objects can only be added to questions with the `by()` method, not the `loop()` method.
This is because the `loop()` method inserts the filepath in the question, whereas the `by()` method inserts the file content when the question is run.

The examples below are also available in a `notebook at Coop <https://www.expectedparrot.com/content/1c1d0d70-9730-4a04-a46e-1b677f9ba521>`_.


File types 
----------

The following file types are currently supported by the `FileStore` module:

* docx (Word document)
* csv (Comma-separated values)
* html (HyperText Markup Language)
* json (JavaScript Object Notation)
* latex (LaTeX)
* md (Markdown)
* pdf (Portable Document Format)
* png (image)
* pptx (PowerPoint)
* py (Python)
* sql (SQL database)
* sqlite (SQLite database)
* txt (text)


Posting a file
--------------

To post a file, import the `FileStore` constructor and create an object by passing the path to the file.
The constructor will automatically infer the file type from the extension.

Then call the `push` method to store the file on the Coop and get a URL and uuid for accessing it.
You can optionally pass a `description` and `visibility` parameter to the `push` method (Coop objects can be *public*, *private* or *unlisted* by default).

The `push` method returns a dictionary with the following keys and values (this is the same for any object posted to Coop):

* `description`: the description of the file
* `object_type`: the type of object (e.g., scenario)
* `url`: the URL of the file on the Coop
* `uuid`: the Coop uuid of the file
* `version`: the version of the file
* `visibility`: the visibility of the file (e.g., public, private, unlisted)


Retrieving a file
-----------------

To retrieve a file, call the `pull` method on the `FileStore` constructor and pass it the Coop uuid of the file that you want to retrieve.

Once retrieved, a file can be converted into a scenario or scenario list.
To construct a single scenario from a file, use the `Scenario` constructor and pass the file as a value for a specified key (see image file example below).
To construct a list of scenarios from a file, call the `from_csv` or `from_pdf` method of the `ScenarioList` constructor and pass the file as an argument (see CSV and PDF examples below).

We can also create agents by calling the `from_csv()` method on an `AgentList` object.


CSV example
^^^^^^^^^^^

Here we create an example CSV and then post it to Coop using `FileStore` and retrieve it.
Then we use the retrieved file to construct scenarios for questions (you can skip the step to create a CSV and replace with your own file).

To create an example CSV file:

.. code-block:: python

    # Sample data
    data = [
        ['Age', 'City', 'Occupation'],
        [25, 'New York', 'Software Engineer'],
        [30, 'San Francisco', 'Teacher'],
        [35, 'Chicago', 'Doctor'],
        [28, 'Boston', 'Data Scientist'],
        [45, 'Seattle', 'Architect']
    ]

    # Writing to CSV file
    with open('data.csv', 'w') as file:
        for row in data:
            line = ','.join(str(item) for item in row)
            file.write(line + '\n')


Here we post the file to Coop and inspect the details:

.. code-block:: python

    from edsl import FileStore

    fs = FileStore("data.csv")
    csv_info = fs.push(description = "My example CSV file", visibility = "public")
    csv_info # display the URL and Coop uuid of the stored file for retrieving it later


Example output:

.. code-block:: python

    {'description': 'My example CSV file',
    'object_type': 'scenario',
    'url': 'https://www.expectedparrot.com/content/371e3ab0-5cf7-4050-89bb-99c5de752fef',
    'uuid': '371e3ab0-5cf7-4050-89bb-99c5de752fef',
    'version': '0.1.39.dev1',
    'visibility': 'public'}


Now we can retrieve the file and create scenarios from it:

.. code-block:: python

    from edsl import FileStore, ScenarioList

    csv_file = FileStore.pull(csv_info["uuid"]) # info is the dictionary returned from the push method above 

    scenarios = ScenarioList.from_csv(csv_file.to_tempfile())
    scenarios # display the scenarios


Output:

.. list-table::
  :header-rows: 1

  * - Age
    - City 
    - Occupation
  * - 25
    - New York
    - Software Engineer
  * - 30
    - San Francisco
    - Teacher
  * - 35
    - Chicago
    - Doctor
  * - 28
    - Boston
    - Data Scientist
  * - 45
    - Seattle
    - Architect


Alternatively, we can create agents from the CSV file:

.. code-block:: python

    from edsl import AgentList

    agents = AgentList.from_csv(csv_file.to_tempfile())


Learn more about designing agents and using scenarios in the :ref:`agents` and :ref:`scenarios` sections.


PNG example
^^^^^^^^^^^

Here we post and retrieve an image file, and then create a scenario for it.
Note that we need to specify the scenario key for the file when we create the scenario.
We also need to ensure that we have specified a vision model when using it with a survey (e.g., GPT-4o).

To post the file:

.. code-block:: python

    from edsl import FileStore

    fs = FileStore("parrot_logo.png") # replace with your own file
    png_info = fs.push()
    png_info # display the URL and Coop uuid of the stored file for retrieving it later


Example output (showing the default description and visibility setting):

.. code-block:: python

    {'description': 'File: parrot_logo.png', 
    'object_type': 'scenario', 
    'url': 'https://www.expectedparrot.com/content/148e6320-5642-486c-9332-a6d30be0daae', 
    'uuid': '148e6320-5642-486c-9332-a6d30be0daae', 
    'version': '0.1.33.dev1', 
    'visibility': 'unlisted'}


Here we retrieve the file and then create a `Scenario` object for it with a key for the placeholder in the questions where we want to use the image:

.. code-block:: python

    from edsl import FileStore, Scenario
    
    png_file = FileStore.pull(png_info["uuid"])
    
    scenario = Scenario({"parrot_logo":png_file}) # including a key for the scenario object


We can verify the key for the scenario object:

.. code-block:: python

    scenario.keys()


Output:

.. code-block:: python

    ['parrot_logo']


To rename a key:

.. code-block:: python

    scenario = scenario.rename({"parrot_logo": "logo"})
    scenario,keys()


Output:

.. code-block:: python

    ['logo']


To use it in a question, the question should be parameterized with the key:

.. code-block:: python

    from edsl import QuestionFreeText 

    q = QuestionFreeText(
        question_name = "test",
        question_text = "Describe this logo: {{ logo }}"
    )


Here we run the question with the scenario object.
Note that we need to use a vision model; here we specify the default model for demonstration purposes and add an agent persona:

.. code-block:: python

    from edsl import Model

    model = Model("gpt-4o") # specify a vision model

    results = q.by(scenario).by(model).run() # run the question with the scenario and model


Learn more about selecting models in the :ref:`language_models` section.

Output:

.. list-table::
  :header-rows: 1

  * - model
    - scenario.logo
    - answer.test
  * - gpt-4
    - FileStore: self.path
    - The logo features a large, stylized letter "E" in a serif font on the left. Next to it, within square brackets, is a colorful parrot. The parrot has a green body, an orange beak, a pink chest, blue lower body, and gray feet. The design combines a classic typographic element with a vibrant, playful illustration.


PDF example
^^^^^^^^^^^

Here we download an example PDF from the internet, post and retrieve it from Coop using `FileStore` and then convert it into a `ScenarioList` object with the `from_pdf()` method.
The default keys are `filename`, `page`, `text`, which can be modified with the `rename` method.

To download a PDF file:

.. code-block:: python

    import requests

    url = "https://arxiv.org/pdf/2404.11794" 
    response = requests.get(url)
    with open("automated_social_scientist.pdf", "wb") as file:
        file.write(response.content)


Here we post the file to Coop and inspect the details:

.. code-block:: python

    from edsl import FileStore

    fs = FileStore("automated_social_scientist.pdf")
    pdf_info = fs.push(description = "My example PDF file", visibility = "public")
    pdf_info # display the URL and Coop uuid of the stored file for retrieving it later


Example output:

.. code-block:: python

    {'description': 'My example PDF file',
    'object_type': 'scenario',
    'url': 'https://www.expectedparrot.com/content/8f4257bf-1b90-473a-a7d5-c7b926b8f104',
    'uuid': '8f4257bf-1b90-473a-a7d5-c7b926b8f104',
    'version': '0.1.39.dev1',
    'visibility': 'public'}


Now we retrieve the file and create a `ScenarioList` object from it:

.. code-block:: python

    from edsl import FileStore, ScenarioList

    pdf_file = FileStore.pull(pdf_info["uuid"])
    
    scenarios = ScenarioList.from_pdf(pdf_file.to_tempfile())


To inspect the keys:

.. code-block:: python

    scenarios.parameters


Output:

.. code-block:: python

    {'filename', 'page', 'text'}


Using the scenarios in a question:

.. code-block:: python

    from edsl import QuestionFreeText

    q = QuestionFreeText(
        question_name = "summary",
        question_text = "Summarize this page: {{ text }}"
    )


Each result will contain the text from a page of the PDF file, together with columns for the filename and page number.
Run `results.columns` to see all the components of results.


FileStore class
---------------

.. automodule:: edsl.scenarios.FileStore
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: 
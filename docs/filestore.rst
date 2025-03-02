.. _filestore:

File Store
==========

`FileStore` is a module for storing and sharing data files at Coop.
It allows you to post and retrieve files of various types to use in EDSL surveys, such as survey data, PDFs, CSVs, docs or images.
It can also be used to create `Scenario` objects for questions or traits for `Agent` objects from data files at Coop.

When posting files, the `FileStore` module will automatically infer the file type from the extension.
You can give a file a `description` and an `alias`, and set its `visibility` (public, private or unlisted).

*Note:* Scenarios created from `FileStore` objects cannot be used with question memory rules, and can only be added to questions with the `by()` method, not the `loop()` method.
This is because the memory rules and `loop()` method insert the filepath in the question, whereas the `by()` method inserts the file content when the question is run.
See details on these methods at the :ref:`scenarios` section of the documentation.

The examples below are also available in a `notebook at Coop <https://www.expectedparrot.com/content/RobinHorton/my-example-filestore-notebook>`_.


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

1. Import the `FileStore` constructor and create an object by passing the path to the file. 
The constructor will automatically infer the file type from the extension.
For example:

.. code-block:: python

    from edsl import FileStore

    fs = FileStore("my_data.csv") # replace with your own file


2. Call the `push` method to post the file at Coop. 
You can optionally pass the following parameters:

* `description`: a string description for the file 
* `alias`: a convenient Pythonic reference name for the URL for the object, e.g., `my_example_csv`
* `visibility`: either *public*, *private* or *unlisted* (the default is *unlisted*)

.. code-block:: python

    fs.push(description = "My example CSV file", alias = "my-example-csv-file", visibility = "public")


The `push` method returns a dictionary with the following keys and values (this is the same for any object posted to Coop):

* `description`: the description you provided, if any
* `object_type`: the type of object (e.g., scenario, survey, results, agent, notebook; objects posted with `FileStore` are always scenarios)
* `url`: the URL of the file at Coop
* `uuid`: the UUID of the file at Coop
* `version`: the version of the file
* `visibility`: the visibility of the file (*public*, *private* or *unlisted* by default)

Example output:

.. code-block:: python

    {'description': 'My example CSV file',
    'object_type': 'scenario',
    'url': 'https://www.expectedparrot.com/content/17c0e3d3-8d08-4ae0-bc7d-384a56a07e4e',
    'uuid': '17c0e3d3-8d08-4ae0-bc7d-384a56a07e4e',
    'version': '0.1.47.dev1',
    'visibility': 'public'}


Retrieving a file
-----------------

To retrieve a file, call the `pull` method on the `FileStore` constructor and pass it the alias or UUID of the file that you want to retrieve.
For the example above, we can retrieve the file with:

.. code-block:: python

    fs = FileStore.pull("https://www.expectedparrot.com/content/RobinHorton/my-example-csv-file") 


This is equivalent:

.. code-block:: python

    fs = FileStore.pull(csv_info["uuid"])


Once retrieved, a file can be converted into scenarios.
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
    csv_info = fs.push(description = "My example CSV file", alias = "my-example-csv-file", visibility = "public")
    csv_info # display the URL and Coop uuid of the stored file for retrieving it later


Example output:

.. code-block:: python

    {'description': 'My example CSV file',
    'object_type': 'scenario',
    'url': 'https://www.expectedparrot.com/content/17c0e3d3-8d08-4ae0-bc7d-384a56a07e4e',
    'uuid': '17c0e3d3-8d08-4ae0-bc7d-384a56a07e4e',
    'version': '0.1.47.dev1',
    'visibility': 'public'}


Now we can retrieve the file and create scenarios from it:

.. code-block:: python

    fs = FileStore.pull("https://www.expectedparrot.com/content/RobinHorton/my-example-csv-file") 

    # or equivalently
    fs = FileStore.pull(csv_info["uuid"])


Here we create a `ScenarioList` object from the CSV file:

.. code-block:: python

    from edsl import ScenarioList

    scenarios = ScenarioList.from_csv(fs.to_tempfile())


To inspect the scenarios:

.. code-block:: python

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

    agents = AgentList.from_csv(fs.to_tempfile())


Learn more about designing agents and using scenarios in the :ref:`agents` and :ref:`scenarios` sections.


PNG example
^^^^^^^^^^^

Here we post and retrieve an image file, and then create a scenario for it.
Note that we need to specify the scenario key for the file when we create the scenario.
We also need to ensure that we have specified a vision model when using it with a survey (e.g., *gpt-4o*).

To post the file:

.. code-block:: python

    from edsl import FileStore

    fs = FileStore("parrot_logo.png") # replace with your own file
    png_info = fs.push(description = "My example PNG file", alias = "my-example-png-file", visibility = "public")
    png_info # display the URL and Coop uuid of the stored file for retrieving it later 


Example output:

.. code-block:: python

    {'description': 'My example PNG file',
    'object_type': 'scenario',
    'url': 'https://www.expectedparrot.com/content/b261660e-11a3-4bec-8864-0b6ec76dfbee',
    'uuid': 'b261660e-11a3-4bec-8864-0b6ec76dfbee',
    'version': '0.1.47.dev1',
    'visibility': 'public'}


Here we retrieve the file and then create a `Scenario` object for it with a key for the placeholder in the questions where we want to use the image:

.. code-block:: python

    from edsl import FileStore
    
    fs = FileStore.pull("https://www.expectedparrot.com/content/RobinHorton/my-example-png-file") 

    # or equivalently
    fs = FileStore.pull(png_info["uuid"])


Here we create a `Scenario` object from the image file:

.. code-block:: python

    from edsl import Scenario

    image_scenario = Scenario({"parrot_logo": fs}) # specify the key for the image


We can verify the key for the scenario object:

.. code-block:: python

    image_scenario.keys()


Output:

.. code-block:: python

    ['parrot_logo']


To rename a key:

.. code-block:: python

    image_scenario = image_scenario.rename({"parrot_logo": "logo"}) # key = old name, value = new name
    image_scenario.keys()


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

    results = q.by(image_scenario).by(model).run() # run the question with the scenario and model


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
    'url': 'https://www.expectedparrot.com/content/e1770915-7e69-436d-b2ca-f0f92c6f56ba',
    'uuid': 'e1770915-7e69-436d-b2ca-f0f92c6f56ba',
    'version': '0.1.47.dev1',
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
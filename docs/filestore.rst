.. _filestore:

File Store
==========

`FileStore` is a module for storing and sharing data on the Coop that you want to use in your EDSL projects, such as survey data, PDFs, CSVs or images.
It can be particularly useful for storing files to be used as as `Scenario` objects with a survey, and allows you to include code for retrieving and processing the files in your EDSL project.


File types 
----------

The following file types are supported by the FileStore:

- CSV
- PDF
- PNG 


Posting a file
--------------

To store a file, you need to create a `FileStore` object with the path to the file you want to store.
You can then use the `push` method to store the file on the Coop and get a URL for accessing the file.

CSV example:

.. code-block:: python

    from edsl.scenarios.FileStore import CSVFileStore

    fs = CSVFileStore("example.csv")
    info = fs.push()
    print(info) # display the URL and Coop uuid of the stored file for retrieving it later


Example output:

.. code-block:: python

    {'description': 'File: example.csv', 
    'object_type': 'scenario', 
    'url': 'https://www.expectedparrot.com/content/4531d6ac-5425-4c93-aa02-07c1fa64aaa3', 
    'uuid': '4531d6ac-5425-4c93-aa02-07c1fa64aaa3', 
    'version': '0.1.33.dev1', 
    'visibility': 'unlisted'}


PDF example:

.. code-block:: python

    from edsl.scenarios.FileStore import PDFFileStore

    fs = PDFFileStore("top_secret.pdf")
    info = fs.push()
    print(info) # display the URL and Coop uuid of the stored file for retrieving it later


Example output:

.. code-block:: python

    {'description': 'File: top_secret.pdf', 
    'object_type': 'scenario', 
    'url': 'https://www.expectedparrot.com/content/a6231668-3166-4741-93d8-f3248b91660f', 
    'uuid': 'a6231668-3166-4741-93d8-f3248b91660f', 
    'version': '0.1.33.dev1', 
    'visibility': 'unlisted'}


PNG example:

.. code-block:: python

    from edsl.scenarios.FileStore import PNGFileStore

    fs = PNGFileStore("parrot_logo.png")
    info = fs.push()
    print(info) # display the URL and Coop uuid of the stored file for retrieving it later


Example output:

.. code-block:: python

    {'description': 'File: parrot_logo.png', 
    'object_type': 'scenario', 
    'url': 'https://www.expectedparrot.com/content/148e6320-5642-486c-9332-a6d30be0daae', 
    'uuid': '148e6320-5642-486c-9332-a6d30be0daae', 
    'version': '0.1.33.dev1', 
    'visibility': 'unlisted'}


Retrieving and using a file
---------------------------

To retrieve a file, you need to create a `FileStore` object with the Coop uuid of the file you want to retrieve.
You can then use the `pull` method to retrieve the file from the Coop.

Once you have retrieved a file, you can use it in your EDSL project as a `Scenario` object.
Each file type has a method for converting the file into a scenario:

- `from_csv` for CSV files
- `from_pdf` for PDF files
- `from_image` for PNG files


CSV example
^^^^^^^^^^^

For CSV files we use the `from_csv` method of the `ScenarioList` class.
They keys are the column names of the CSV file, which can be modified with the `rename` method.

.. code-block:: python

    from edsl.scenarios.FileStore import CSVFileStore
    from edsl import ScenarioList
    
    csv_file = CSVFileStore.pull("4531d6ac-5425-4c93-aa02-07c1fa64aaa3", expected_parrot_url="https://www.expectedparrot.com")

    scenarios = ScenarioList.from_csv(csv_file.to_tempfile())


PDF example
^^^^^^^^^^^

For PDF files we use the `from_pdf` method of the `ScenarioList` class.
The default keys are `filename`, `page`, `text`, which can be modified with the `rename` method.

.. code-block:: python

    from edsl.scenarios.FileStore import PDFFileStore
    from edsl import ScenarioList

    pdf_file = PDFFileStore.pull("a6231668-3166-4741-93d8-f3248b91660f", expected_parrot_url="https://www.expectedparrot.com")
    
    scenario = ScenarioList.from_pdf(pdf_file.to_tempfile())


To inspect the keys:

.. code-block:: python

    scenario.parameters


Output:

.. code-block:: python

    {'filename', 'page', 'text'}


PNG example
^^^^^^^^^^^

For PNG files we use the `from_image` method which takes the PNG file and (optionally) the name of a key to use for the scenario object.

.. code-block:: python

    from edsl.scenarios.FileStore import PNGFileStore
    from edsl import Scenario
    
    png_file = PNGFileStore.pull("148e6320-5642-486c-9332-a6d30be0daae", expected_parrot_url="https://www.expectedparrot.com")

    scenario = Scenario.from_image(png_file.to_tempfile(), "parrot_logo") # including a key for the scenario object


Working with scenarios 
----------------------

Before using the scenario, verify the key and value of the scenario object (e.g., by printing), and rename the key as desired to use in survey questions.

For a single `Scenario` we can check the key:

.. code-block:: python

    scenario.keys()


(For a `ScenarioList` object, we can call the `parameters` method to get the keys.)

If the key is `parrot_logo` and you want to rename it `logo`:

.. code-block:: python

    scenario = scenario.rename({"parrot_logo": "logo"})


To use it in a question, the question should be parameterized with the key:

.. code-block:: python

    from edsl import QuestionFreeText 

    q = QuestionFreeText(
        question_name = "test",
        question_text = "What is the logo of the company? {{ logo }}"
    )

    results = q.by(scenario).run()


Example notebook
----------------

The following notebook at the Coop includes the above code examples: https://www.expectedparrot.com/content/e1a00873-dfc6-4383-9426-cc032296bab1


FileStore class
---------------

.. automodule:: edsl.scenarios.FileStore
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: 
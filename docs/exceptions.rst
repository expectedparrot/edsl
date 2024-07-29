.. _exceptions:

Exceptions & Debugging
======================

An exception is an error that occurs during the execution of a question or survey. 
When an exception is raised, EDSL will display a message about the error that includes a link to a report with more details.

Example 
-------

Here's an example of a poorly written question that is likely to raise an exception:

.. code-block:: python

    from edsl.questions import QuestionMultipleChoice

    q = QuestionMultipleChoice(
        question_name = "bad_instruction",
        question_text = "What is your favorite color?",
        question_options = ["breakfast", "lunch", "dinner"] # Non-sensical options for the question
    )

    results = q.run()


The above code will likely raise a `QuestionAnswerValidationError` exception because the question options are not related to the question text.
Output:

.. code-block:: text

    Attempt 1 failed with exception:Answer code must be a string, a bytes-like object or a real number (got Invalid). now waiting 1.00 seconds before retrying.Parameters: start=1.0, max=60.0, max_attempts=5.


    Attempt 2 failed with exception:Answer code must be a string, a bytes-like object or a real number (got The question asks for a favorite color, but the options provided are meal times, not colors. Therefore, I cannot select an option that accurately reflects a favorite color.). now waiting 2.00 seconds before retrying.Parameters: start=1.0, max=60.0, max_attempts=5.


    Attempt 3 failed with exception:Answer code must be a string, a bytes-like object or a real number (got The question does not match the provided options as they pertain to meals, not colors.). now waiting 4.00 seconds before retrying.Parameters: start=1.0, max=60.0, max_attempts=5.


    Attempt 4 failed with exception:Answer code must be a string, a bytes-like object or a real number (got This is an invalid question since colors are not listed as options. The options provided are meals, not colors.). now waiting 8.00 seconds before retrying.Parameters: start=1.0, max=60.0, max_attempts=5.


    Exceptions were raised in 1 out of 1 interviews.

    Open report to see details.


Exceptions report 
-----------------

The exceptions report can be accessed by clicking on the link provided in the exceptions message that is generated when exceptions are raised during the execution of the survey.
It contains details on the exceptions that were raised:

.. image:: ../_static/exceptions_message.png
    :width: 800
    :align: center


Performance plot 
^^^^^^^^^^^^^^^^

The report includes a **Performance Plot** (scroll to the end of the report to view it):

.. image:: ../_static/exceptions_performance_plot.png
    :width: 800
    :align: center


Help debugging
--------------

If you would like help debugging an error that you are encountering, please feel free to share your code, objects and exceptions report with us.

A simple way to do this is to post a :ref:`notebook` with your code to the :ref:`coop` and share the link with us at info@expectedparrot.com.
You can use the following code to generate a link to your notebook:

.. code-block:: python

    from edsl import Coop, notebook

    coop = Coop()

    notebook = Notebook(path="path/to/your/notebook.ipynb")

    coop.create(notebook, description="Notebook with code that raises an exception", visibility="private")


A notebook showing the above example question and exception message is available at the Coop: https://www.expectedparrot.com/content/f6a19c77-3f57-4900-b0c9-436058a2ad27


Common exceptions
-----------------

Answer validation errors
^^^^^^^^^^^^^^^^^^^^^^^^

A number of exceptions may indicate that there is a problem with the way that a question has been constructed or answered.
For example, you may except a list as an answer but receive a string instead, or `None`.
These exceptions are typically raised by the `Question` class and are subclassed from `QuestionAnswerValidationError`.

A useful starting point for debugging these exceptions is to check the `Settings` class for the `Questions` model.
The default setting are as follows:

.. code-block:: python

    MAX_ANSWER_LENGTH = 2000
    MAX_EXPRESSION_CONSTRAINT_LENGTH = 1000
    MAX_NUM_OPTIONS = 200
    MIN_NUM_OPTIONS = 2
    MAX_OPTION_LENGTH = 10000
    MAX_QUESTION_LENGTH = 100000


JSON errors
^^^^^^^^^^^

Some exceptions may indicate that the response from the language model is not properly formatted JSON.
This can be caused by a problem with the inference provider or the way that the question has been constructed.
A useful starting point for debugging these exceptions is to check the `Settings` class for the `Questions` model.
See *Answer validation errors* above.


Missing API key 
^^^^^^^^^^^^^^^

You will receive a `MissingAPIKeyError` exception if you try to run a question and have not activated :ref:`remote_inference` or stored an API key for the model that you are trying to use.


Problem with inference provider
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Some exceptions may indicate that there is a problem with your account with an inference provider, such as insufficient credits.


API Timeout
^^^^^^^^^^^

The maximum number of seconds to wait for an API call to return can be specified in `config.py`:

.. code-block:: python

CONFIG_MAP = {
    ...
    "EDSL_API_TIMEOUT": {
        "default": "60",
        "info": "This env var determines the maximum number of seconds to wait for an API call to return.",
    },
    ...
    

Missing packages
^^^^^^^^^^^^^^^^

A `ModuleNotFoundError` exception will be raised if a required package is not installed. 
This is more likely to occur when cloning the repository instead of installing the package using `pip install edsl`.
It can typically be remedied by reinstalling your virtual environment or installing the missing package using `pip install <package_name>`.


Strategies for dealing with exceptions
--------------------------------------

Re-try the question
^^^^^^^^^^^^^^^^^^^

If an exception is raised, the question will be re-tried up to a maximum number of attempts.
The number of retries can be specified in `config.py`:

.. code-block:: python

CONFIG_MAP = {
    ...
    "EDSL_MAX_ATTEMPTS": {
        "default": "5",
        "info": "This env var determines the maximum number of times to retry a failed API call.",
    },
    ...


By default, your successul results are cached, so rerunning a survey will only re-run the questions that were not answered successfully in the previous run
(i.e., you do not need to specify which questions to re-run if the survey is not modified).
Learn more about working with :ref:`data`. 


Search for the exception message in the documentation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The name of the exception that is raised will often provide a clue as to what the problem is.
You can search for the exception type in the search bar at the top of the main documentation page to find more information about the exception and how to resolve it.
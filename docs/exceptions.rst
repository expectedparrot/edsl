.. _exceptions:

Exceptions & Debugging
======================

An exception is an error that occurs during the execution of a question or survey. 
When an exception is raised, EDSL will display a message about the error and an interactive report with more details in a new browser tab.


Help debugging
--------------

If you would like help debugging an error that you are encountering, please feel free to share your code, objects and exceptions report with us.

An easy way to do this is to post a notebook with your code to the :ref:`coop` and **share the link with us at info@expectedparrot.com**.
You can use the following code to generate a link to your notebook:

.. code-block:: python

    from edsl import notebook

    n = Notebook(path="path/to/your/notebook.ipynb")

    n.push(description="Notebook with code that raises an exception", visibility="private")



Common exceptions
-----------------

Answer validation errors
^^^^^^^^^^^^^^^^^^^^^^^^

A number of exceptions may indicate that there is a problem with the way that a question has been constructed or answered.
For example, you may intend for the answer to be formatted as a list but receive a string instead.
Or a question may be unanswered and the model has returned `None`.
These exceptions are typically raised by the `Question` class and are subclassed from `QuestionAnswerValidationError`.

A useful starting point for debugging these exceptions is to check the `Settings` class for the `Questions` model (https://github.com/expectedparrot/edsl/blob/main/edsl/questions/settings.py).
The default settings (which can be modified) are as follows:

.. code-block:: python

    MAX_ANSWER_LENGTH = 2000
    MAX_EXPRESSION_CONSTRAINT_LENGTH = 1000
    MAX_NUM_OPTIONS = 200
    MIN_NUM_OPTIONS = 2
    MAX_OPTION_LENGTH = 10000
    MAX_QUESTION_LENGTH = 100000


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

Show full tracebacks
^^^^^^^^^^^^^^^^^^^

By default, EDSL simplifies exception messages by hiding the full Python traceback. This makes error messages cleaner and easier to read for most users.

When developing with EDSL or debugging issues, you may want to see the full traceback to better understand where the error is occurring. You can enable full tracebacks by setting the `EDSL_SHOW_FULL_TRACEBACK` environment variable:

.. code-block:: python

    # Option 1: Set environment variable in your Python code
    import os
    os.environ["EDSL_SHOW_FULL_TRACEBACK"] = "True"

    # Option 2: Add to your .env file
    # EDSL_SHOW_FULL_TRACEBACK=True

The value is not case-sensitive and can be any of the following:

- "True", "1", "yes", "y" to show full tracebacks
- Any other value (including "False") to use the default behavior

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


By default, your successful results are cached, so re-executing a survey will only re-run the questions that were not answered successfully in the previous run.
Learn more about working with :ref:`data`. 


Search for the exception message in the documentation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The name of the exception that is raised will often provide a clue as to what the problem is.
You can search for the exception type in the search bar at the top of the main documentation page to find more information about the exception and how to resolve it.
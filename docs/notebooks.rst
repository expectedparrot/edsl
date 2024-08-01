.. _notebooks:

Notebooks
=========

The `Notebook` object allows you to share your .ipynb files with others by uploading them to Coop.
You can also view and pull notebooks that other users have uploaded.

Creating a `Notebook` object
----------------------------

There are three ways to create a `Notebook` object:

1. From file
^^^^^^^^^^^^
Pass the path to your .ipynb file to the constructor (you must include `path` as a keyword argument):

.. code-block:: python

    from edsl import Notebook

    notebook = Notebook(path="notebooks/test-notebook.ipynb")


2. From data
^^^^^^^^^^^^
Your data must be a Python `dict` that conforms to the official Jupyter notebook format. 
Learn more about the format `here <https://nbformat.readthedocs.io/en/latest/format_description.html>`_.

.. code-block:: python

    from edsl import Notebook

    data = {
        "metadata": dict(),
        "nbformat": 4,
        "nbformat_minor": 4,
        "cells": [
            {
                "cell_type": "markdown",
                "metadata": dict(),
                "source": "# Test notebook",
            },
        ],
    }

    notebook = Notebook(data=data)


3. From self
^^^^^^^^^^^^
To create a `Notebook` for a notebook that you are currently working in:

.. code-block:: python

    from edsl import Notebook

    # Do not pass any arguments to the constructor
    notebook = Notebook()


.. warning::
    For now, this method only works if you are using the VS Code IDE. 

    
Uploading a notebook to Coop
----------------------------

A notebook can be posted to Coop in the same ways as other EDSL objects: by calling the `push()` method on the `Notebook` object or calling the `create` method on a `Coop` object and passing it the notebook.
The `description` and `visibility` arguments are optional and can be modified later:

.. code-block:: python

    from edsl import Notebook

    notebook = Notebook(path="model_votes.ipynb")

    notebook.push(description="Comparing model votes", visibility="public")


Or alternatively using the `Coop` client object:

.. code-block:: python

    from edsl import Coop, Notebook

    coop = Coop()

    notebook = Notebook(path="model_votes.ipynb")

    coop.create(notebook, description="Comparing model votes", visibility="public")


This will return a message with information about the object that was posted, and you will be able to view your notebook at the Coop: `My Content  <https://www.expectedparrot.com/home/content/>`_.

.. code-block:: text

  {'description': 'Comparing model votes',
  'object_type': 'notebook',
  'url': 'https://www.expectedparrot.com/content/1234abcd-abcd-1234-abcd-1234abcd1234',
  'uuid': '1234abcd-abcd-1234-abcd-1234abcd1234',
  'version': '0.1.30',
  'visibility': 'public'}


Saving a Coop notebook to file
------------------------------

You can access notebooks that other users have posted publicly at the `Explore <https://www.expectedparrot.com/explore/explore/>`_ page.

Notebooks can be copied and downloaded the same way as other EDSL objects: by calling the `pull()` method on the `Notebook` class or the `get` method on a `Coop` client object and passing the notebook's `uuid`.
We can also use the `to_file()` method to save the notebook to a file:

.. code-block:: python

    from edsl import Notebook

    notebook = Notebook.pull("05dbaf7c-1f82-44e1-9aef-d67a3108915c")

    notebook.to_file("grading_experiment.ipynb")


This allows you to edit and run the notebook on your local machine.

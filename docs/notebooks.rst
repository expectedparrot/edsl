.. _notebooks:

Notebooks
=========

The `Notebook` object allows you to share your notebooks and scripts (*.ipynb* and *.py* files) by uploading them to Coop.
You can also view and pull notebooks that other users have shared publicly or privately with you.


Special note for Colab users
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are using EDSL in a Colab notebook, please see `special instructions <https://docs.expectedparrot.com/en/latest/colab_notebooks.html>`_ on posting Colab notebooks to Coop (:ref:`colab_notebooks`).


Creating a `Notebook` object
----------------------------

There are three ways to create a `Notebook` object:


1. From a *.ipynb* file
^^^^^^^^^^^^^^^^^^^^^^^

Pass the path to your *.ipynb* file to the constructor:

.. code-block:: python

    from edsl import Notebook

    notebook = Notebook("your_notebook.ipynb") # replace with your file path


*Note:* You first need to save your notebook in order to pass the `path=<filename>` argument to the constructor.

2. From a *.py* script
^^^^^^^^^^^^^^^^^^^^^^

Call the `from_script()` method on the constructor and pass it the path to your *.py* script:

.. code-block:: python

    from edsl import Notebook

    notebook = Notebook.from_script("your_script.py") # replace with your script path


3. From data
^^^^^^^^^^^^

For this method, your data must be a Python `dict` that conforms to the official Jupyter notebook format. 
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


4. From self
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

A notebook can be posted to Coop in the same ways as other EDSL objects: by calling the `push()` method on the object or calling the `create` method on a `Coop` object and passing it the notebook.

Here we create a `Notebook` object and use the `push()` method to post it to Coop.
You can optionally pass a `description`, a convenient `alias` for the Coop URL and a `visibility` setting (*public*, *private* or *unlisted* by default) to the `push()` method:

.. code-block:: python

    from edsl import Notebook

    notebook = Notebook("demo_notebook.ipynb")

    notebook.push(
        description = "This is a demo notebook", 
        alias = "demo-notebook",
        visibility = "public"
    ) 


These can also be modified at Coop later on.
We can see that the notebook has been posted publicly with a description and an alias URL (you can retrieve and refer to the object by either the UUID or URL):

.. code-block:: text

    {'description': 'This is a demo notebook',
    'object_type': 'notebook',
    'url': 'https://www.expectedparrot.com/content/121e2904-e09e-4859-80d5-dc98cb8c537a',
    'alias_url': 'https://www.expectedparrot.com/content/RobinHorton/demo-notebook',
    'uuid': '121e2904-e09e-4859-80d5-dc98cb8c537a',
    'version': '0.1.47.dev1',
    'visibility': 'public'}


Here we alternatively use the `Coop` client object to post the notebook:

.. code-block:: python

    from edsl import Coop, Notebook

    coop = Coop()

    notebook = Notebook("demo_notebook.ipynb")

    coop.create(notebook, description="This is a demo notebook", visibility="public")


(Note that we cannot reuse the alias unless we delete the object.)
This will return a message with information about the object that was posted, and you will be able to view your notebook at the Coop: `Content  <https://www.expectedparrot.com/home/content>`_.


Updating a notebook on Coop
---------------------------

A notebook can be updated on Coop in the same ways as other EDSL objects: by calling the `patch()` method on the object or calling the `update` method on a `Coop` object and passing it the parameters to be modified.

Here we update the `description` of a notebook that we have already posted:

.. code-block:: python

    from edsl import Notebook

    notebook = Notebook.pull("https://www.expectedparrot.com/content/RobinHorton/demo-notebook")

    notebook.patch(
        "https://www.expectedparrot.com/content/RobinHorton/demo-notebook", 
        description = "This is an updated demo notebook"
        )


Here we alternatively use the `Coop` client object:

.. code-block:: python

    from edsl import Coop

    c = Coop()  

    c.patch(
        "121e2904-e09e-4859-80d5-dc98cb8c537a",
        description = "This is an updated demo notebook"
        )  


Here we update the contents of the notebook itself by passing the `value` argument:

.. code-block:: python

    notebook = Notebook("demo_notebook.ipynb") # resaving the notebook

    notebook.patch(
        "121e2904-e09e-4859-80d5-dc98cb8c537a", 
        value = notebook
        )


Saving a Coop notebook to file
------------------------------

You can access notebooks that other users have posted publicly at the Coop `Content <https://www.expectedparrot.com/content/explore>`_ page.

Notebooks can be copied and downloaded the same way as other EDSL objects: by calling the `pull()` method on the `Notebook` constructor or the `get` method on a `Coop` client object and passing the notebook's `uuid`.
You can also use the `to_file()` method to save the notebook to a file:

.. code-block:: python

    from edsl import Notebook

    notebook = Notebook.pull("121e2904-e09e-4859-80d5-dc98cb8c537a",)

    notebook.to_file("new_demo_notebook.ipynb")


This allows you to edit and run the notebook on your local machine.


Deleting a notebook from Coop
-----------------------------

A notebook can be deleted from Coop in the same ways as other EDSL objects: by calling the `delete()` method on the constructor and passing it the `uuid` of the notebook to be deleted.
You can also delete a notebook manually from your Coop account.

Here we delete a notebook using the `Notebook` object:

.. code-block:: python

    from edsl import Notebook

    Notebook.delete(uuid = "121e2904-e09e-4859-80d5-dc98cb8c537a",)
.. _notebooks:

Notebooks
=========

The `Notebook` object allows you to share your notebooks and scripts (*.ipynb* and *.py* files) by uploading them to Coop.
You can also view and pull notebooks that other users have shared publicly or privately with you.

Examples of methods below are also viewable in `this notebook at the Coop <https://www.expectedparrot.com/content/ffa113f4-4f2a-407b-8fc6-27bdf5e69d2f>`_.


Special note for Colab users
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you are using EDSL in a Colab notebook, please see `special instructions <https://docs.expectedparrot.com/en/latest/colab_notebooks.html>`_ on posting Colab notebooks to Coop (:ref:`colab_notebooks`).


Creating a `Notebook` object
----------------------------

There are three ways to create a `Notebook` object:


1. From a *.ipynb* file
^^^^^^^^^^^^^^^^^^^^^^^

Pass the path to your *.ipynb* file to the constructor (*note:* you must include `path` as a keyword argument):

.. code-block:: python

    from edsl import Notebook

    notebook = Notebook(path="your_notebook.ipynb") # replace with your file path


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

Here we create a `Notebook` object and use the `push()` method to post it to Coop:

.. code-block:: python

    from edsl import Notebook

    notebook = Notebook(path="demo_notebook.ipynb")

    notebook.push()


This will return a message with information about the object that was posted, and you will be able to view your notebook at the Coop: `Content  <https://www.expectedparrot.com/home/content>`_:

.. code-block:: text

    {'description': None,
    'object_type': 'notebook',
    'url': 'https://www.expectedparrot.com/content/fc671612-4144-4da3-a7b5-23587cc5a788',
    'uuid': 'fc671612-4144-4da3-a7b5-23587cc5a788',
    'version': '0.1.36.dev1',
    'visibility': 'unlisted'}


We can see that the notebook has at an unlisted (non-searchable) URL with no description.
We can edit the description and the visibility status directly at the Coop or by passing the arguments to the `push()` method:

.. code-block:: python

    from edsl import Notebook

    notebook = Notebook(path="demo_notebook.ipynb")

    notebook.push(description="This is a demo notebook", visibility="public") # add description and make it public


We can see that the notebook has been reposted publicly with a description:

.. code-block:: text

    {'description': 'This is a demo notebook',
    'object_type': 'notebook',
    'url': 'https://www.expectedparrot.com/content/1742e39d-9f6d-4997-bfea-eda99120cf06',
    'uuid': '1742e39d-9f6d-4997-bfea-eda99120cf06',
    'version': '0.1.36.dev1',
    'visibility': 'public'}


Here we alternatively use the `Coop` client object to post the notebook:

.. code-block:: python

    from edsl import Coop, Notebook

    coop = Coop()

    notebook = Notebook(path="demo_notebook.ipynb")

    coop.create(notebook, description="This is a demo notebook", visibility="public")


This will return a message with information about the object that was posted, and you will be able to view your notebook at the Coop: `Content  <https://www.expectedparrot.com/home/content>`_.

.. code-block:: text

    {'description': 'This is a demo notebook',
    'object_type': 'notebook',
    'url': 'https://www.expectedparrot.com/content/ffa113f4-4f2a-407b-8fc6-27bdf5e69d2f',
    'uuid': 'ffa113f4-4f2a-407b-8fc6-27bdf5e69d2f',
    'version': '0.1.35',
    'visibility': 'public'}


Updating a notebook on Coop
---------------------------

A notebook can be updated on Coop in the same ways as other EDSL objects: by calling the `patch()` method on the object or calling the `update` method on a `Coop` object and passing it the parameters to be modified.

Here we update the `description` of a notebook that we have already posted:

.. code-block:: python

    from edsl import Notebook

    notebook = Notebook.pull("ffa113f4-4f2a-407b-8fc6-27bdf5e69d2f")

    notebook.patch(
        uuid = "ffa113f4-4f2a-407b-8fc6-27bdf5e69d2f", 
        description = "This is an updated demo notebook"
        )


Here we alternatively use the `Coop` client object:

.. code-block:: python

    from edsl import Coop

    c = Coop()  

    c.patch(
        uuid="ffa113f4-4f2a-407b-8fc6-27bdf5e69d2f",
        description = "This is an updated demo notebook"
        )  


Here we update the contents of the notebook itself by passing the `value` argument:

.. code-block:: python

    notebook = Notebook(path="demo_notebook.ipynb") # resaving the notebook

    notebook.patch(
        uuid = "ffa113f4-4f2a-407b-8fc6-27bdf5e69d2f", 
        value = notebook
        )


Saving a Coop notebook to file
------------------------------

You can access notebooks that other users have posted publicly at the Coop `Content <https://www.expectedparrot.com/content>`_ page.

Notebooks can be copied and downloaded the same way as other EDSL objects: by calling the `pull()` method on the `Notebook` constructor or the `get` method on a `Coop` client object and passing the notebook's `uuid`.
You can also use the `to_file()` method to save the notebook to a file:

.. code-block:: python

    from edsl import Notebook

    notebook = Notebook.pull("ffa113f4-4f2a-407b-8fc6-27bdf5e69d2f")

    notebook.to_file("new_demo_notebook.ipynb")


This allows you to edit and run the notebook on your local machine.


Deleting a notebook from Coop
-----------------------------

A notebook can be deleted from Coop in the same ways as other EDSL objects: by calling the `delete()` method on the constructor and passing it the `uuid` of the notebook to be deleted.
You can also delete a notebook manually from your Coop account.

Here we delete a notebook using the `Notebook` object:

.. code-block:: python

    from edsl import Notebook

    Notebook.delete(uuid = "ffa113f4-4f2a-407b-8fc6-27bdf5e69d2f")
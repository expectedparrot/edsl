.. _colab_notebooks:

Colab Notebooks
===============

All of the methods for working with notebooks in EDSL are available in Colab.

To access these methods in Colab, please first complete the following steps to set up EDSL and connect your Google Drive:


1. Store your API key as a secret
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

In Google Colab, your API keys can be stored as "secrets" in lieu of storing them in a *.env* file as you would in other notebook types.

For example, you can store your Expected Parrot API key as follows:

.. image:: static/colab_keys_secrets.png
  :alt: Storing API key in Google Colab
  :align: center
  :width: 80%
  

.. raw:: html

  <br><br>
  

2. Install EDSL
^^^^^^^^^^^^^^^

Run the following command in a code cell to install the EDSL package:

.. code:: python

    pip install edsl


3. Access your API key
^^^^^^^^^^^^^^^^^^^^^^

Run the following code to access your API key in your Colab notebook:

.. code:: python

    import os
    from google.colab import userdata

    os.environ['EXPECTED_PARROT_API_KEY'] = userdata.get('EXPECTED_PARROT_API_KEY') 


4. Connect your Google Drive
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To access your files in Google Drive, you need to connect your Google Drive to Colab.
Run the following code to do this, and accept the permissions request in the pop-up window:

.. code:: python

    from google.colab import drive

    drive.mount('/content/drive')


You will see the following message returned:

.. code:: text

    Drive already mounted at /content/drive; to attempt to forcibly remount, call drive.mount("/content/drive", force_remount=True).



5. Access your files
^^^^^^^^^^^^^^^^^^^^

Run the following code to see the names of all the files in a Google Drive folder

Note that you will need to replace the path with the path to your own folder, and you may need to adjust the path to match the structure of your Google Drive
(e.g., here the default Google Drive folder name "Colab Notebooks" has been changed to "ColabNotebooks" for convenience in specifying the path):

.. code:: python

    import os

    print(sorted(os.listdir('/content/drive/MyDrive/ColabNotebooks/')))


Sample output:

.. code:: python

    ['colab_to_coop.ipynb']


6. Post a notebook to Coop
^^^^^^^^^^^^^^^^^^^^^^^^^^

Now that you have your notebook ready, you can post it to Coop using the `Notebook` object.
Modify the path to your notebook file path in your Google Drive as needed:

.. code:: python

    from edsl import Notebook

    notebook = Notebook(path="/content/drive/MyDrive/ColabNotebooks/colab_to_coop.ipynb")

    notebook.push(description="Posting a Colab notebook to Coop")


Example output:

.. code:: text 

    {'description': 'Posting a Colab notebook to Coop',
    'object_type': 'notebook',
    'url': 'https://www.expectedparrot.com/content/a878656a-317a-4181-a496-3c49f12e38d7',
    'uuid': 'a878656a-317a-4181-a496-3c49f12e38d7',
    'version': '0.1.36',
    'visibility': 'unlisted'}



7. Update or edit a notebook at Coop
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code:: python

    from edsl import Notebook

    notebook = Notebook(path="/content/drive/MyDrive/ColabNotebooks/colab_to_coop.ipynb")

    notebook.patch(
        uuid = "a878656a-317a-4181-a496-3c49f12e38d7",
        visibility = "public",
        value = notebook
        )


Output:

.. code:: text 

    {'status': 'success'}



Example Colab code 
------------------

.. image:: static/colab_notebooks.png
  :alt: Posting a Colab notebook to Coop
  :align: center
  :width: 80%
  

.. raw:: html

  <br><br>
.. _colab_setup:

Colab Setup
===========

All of the examples, tutorials and demo notebooks in this documentation are designed to be executable in any type of Python notebook. 

To run them in Colab, please follow these special instructions for technical setup:


1. Store your API key as a secret
---------------------------------

In Google Colab, your API keys can be stored as "secrets" in lieu of storing them in a *.env* file as you would in other notebook types.

For example, you can store your Expected Parrot API key as follows:

.. image:: static/colab_keys_secrets.png
  :alt: Storing API key in Google Colab
  :align: center
  :width: 80%
  

.. raw:: html

  <br><br>
  

2. Install EDSL
---------------

Run the following command in a code cell to install the EDSL package:

.. code:: python

    pip install edsl


3. Access your API key
----------------------

To access your API key in your code, use the following code snippet:

.. code:: python

    import os
    from google.colab import userdata

    os.environ['EXPECTED_PARROT_API_KEY'] = userdata.get('EXPECTED_PARROT_API_KEY') 


Example Colab code 
------------------

EDSL methods for creating objects and posting them to the Coop are now available to you in Colab.

Here's a snapshot of how your Colab code might look:

.. image:: static/colab_sample_code.png
  :alt: Storing and using API key in Google Colab
  :align: center
  :width: 80%
  

.. raw:: html

  <br><br>


Posting Colab notebooks to Coop
-------------------------------

Special instructions for connecting your Google Drive to post Colab notebooks to Coop are available in the :ref:`colab_notebooks` section.
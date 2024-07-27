.. _installation:

Installation
============
EDSL is a Python library that can be installed through pip. 
It is compatible with Python 3.9 - 3.12.

.. note::

    EDSL is in development. 
    We recommend that you continually check for and install the latest version of EDSL to access the most recent features and bug fixes.


Prerequisites
-------------
Ensure that you have Python installed on your system. 
You can download Python from the `official website <https://www.python.org/downloads/>`_.

Use `pip <https://pip.pypa.io/en/stable/installation/>`_ to install EDSL on your system (a package installer for Python).


Quickstart Installation
-----------------------
Open your terminal and verify that you have not previously installed EDSL by entering the following command:

.. code::

    pip show edsl


If EDSL is already installed, you will see the following output, including the actual version number:

.. code::

    Name: edsl
    Version: 0.1.###
    ...


If EDSL is not installed (`WARNING: Package(s) not found: edsl`), enter the following command to install the latest version with pip:

.. code:: 

    pip install edsl


To confirm that your version is up to date, compare your version number with the latest version on the `EDSL PyPI page <https://pypi.org/project/edsl/>`_.


Updating your version
---------------------
To update your EDSL version to the latest one:

.. code:: 

    pip install --upgrade edsl


Advanced installation
---------------------
Following the steps in Quickstart Installation will install EDSL globally on your system. 
Sometimes, you may face problems with conflicts between EDSL and other libraries. 
To avoid such problems, we recommend that you use a virtual environment.

To create a virtual environment, open your terminal and run the following command:

.. code:: 

    python -m venv myenv


This will create a folder called myenv. Next, activate your virtual environment:

.. code:: 

    source myenv/bin/activate


You can now install EDSL through pip within your virtual environment:

.. code:: 

    pip install edsl


You will have access to EDSL while your virtual environment is activated.

You can deactivate the virtual environment at any time by running:

.. code:: 

    deactivate


To delete the virtual environment, simply delete the myenv folder.

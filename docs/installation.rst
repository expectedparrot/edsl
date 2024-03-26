Installation
============

EDSL is an open-source Python library. The goal of EDSL is to make
AI-powered research easy for beginners, advanced users, and everyone in
between!

In this page we show how to set up EDSL on your system.

Quickstart installation
-----------------------

EDSL is a Python library. To use it, ensure that you have Python
installed in your system and a basic working knowledge of how to write
python code.

Open your terminal and verify that you have not previously installed
EDSL on your system:

.. code:: 

    pip show edsl

To install the latest version of EDSL through pip:

.. code:: 

    pip install edsl

To update your EDSL version to the latest one:

.. code:: 

    pip install --upgrade edsl

Advanced installation
---------------------

Following the steps in Quickstart Installation will install EDSL
globally on your system. Sometimes, you may face problems with conflicts
between EDSL and other libraries. To avoid such problems, we recommend
that you use a virtual environment.

Open your terminal and run the following command:

.. code:: 

    python3 -m venv myenv

This will create a folder called myenv. Next, activate your virtual
environment:

.. code:: 

    source myenv/bin/activate

You can now install EDSL through pip within your virtual environment:

.. code:: 

    pip install edsl

You will have access to EDSL while your virtual environment is
activated.

You can deactivate the virtual environment at any time by running:

.. code:: 

    deactivate

To delete the virtual environment, simply delete the myenv folder.
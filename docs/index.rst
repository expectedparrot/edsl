.. _index:

EDSL: AI-Powered Research
=========================

*Expected Parrot Domain-Specific Language* (EDSL) is an open-source Python package for conducting AI-powered research.
   
.. raw:: html

   EDSL is developed by <a href="https://www.expectedparrot.com" target="_blank">Expected Parrot</a> and available under the MIT License.
   <br><br>

This page provides documentation, tutorials and demo notebooks for the EDSL package and Coop: a platform for creating, storing and sharing AI research.
The contents are organized into key sections to help you get started:

Links
-----

.. raw:: html

   <a href="https://pypi.org/project/edsl" target="_blank"><i class="fab fa-python"></i></a>&nbsp;&nbsp;Download the latest version of EDSL at <a href="https://pypi.org/project/edsl" target="_blank">PyPI</a>.     
   <br><br>

.. raw:: html

   <a href="https://github.com/expectedparrot/edsl" target="_blank"><i class="fab fa-github"></i></a>&nbsp;&nbsp;Get the latest EDSL updates at <a href="https://github.com/expectedparrot/edsl" target="_blank">GitHub</a>.
   <br><br>

.. raw:: html

   <a href="https://discord.com/invite/mxAYkjfy9m" target="_blank"><i class="fab fa-discord"></i></a>&nbsp;&nbsp;<a href="https://discord.com/invite/mxAYkjfy9m" target="_blank">Join our Discord channel</a> to connect with other users and ask questions.
   <br><br>

Introduction
------------

- :ref:`overview`:  An overview of the purpose, concepts and goals of the EDSL package.
- :ref:`whitepaper`:  A whitepaper about the EDSL package (in progress).
- :ref:`citation`:  How to cite the package in your work.

Getting Started
---------------

- :ref:`starter_tutorial`:  A tutorial to help you get started using EDSL.
- :ref:`installation`:  How to install the EDSL package.
- :ref:`api_keys`:  How to store API keys for language models.

Core Concepts
-------------

- :ref:`questions`:  Learn about different question types and applications.
- :ref:`scenarios`:  Explore how questions can be dynamically parameterized for tasks like data labeling.
- :ref:`surveys`:  How to construct surveys and implement rules and conditions.
- :ref:`agents`:  How to design and implement AI agents to respond to surveys.
- :ref:`language_models`:  How to select language models to generate results.
- :ref:`results`:  Explore built-in methods for analyzing and utilizing survey results.
- :ref:`data`:  Learn about caching and sharing results.
- :ref:`exceptions`:  How to identify and handle exceptions in your survey design.
- :ref:`token_limits`:  How to manage token limits for language models.

Importing Data
--------------

- :ref:`conjure`: Automatically import other survey data into EDSL to:
  * Clean and analyze your data.
  * Create AI agents for respondents and conduct follow-on interviews.
  * Extend your results with new questions and surveys.
  * Store and share your data on the Coop.

Coop 
----

- :ref:`coop`: A platform for creating, storing and sharing AI research. 
- :ref:`notebooks`: Instructions for sharing .ipynb files with other users on the Coop. 
- :ref:`remote_caching`: Learn how to cache your results and API calls on our server. 

How-to Guides
-------------

Examples of special methods and use cases, such as data labeling tasks, cognitive testing, dynamic agent traits and creating new methods.

Notebooks
---------

A variety of templates and examples for using the package to conduct different kinds of research.
*We're happy to create a new notebook for your use case!*

Developers
----------

Information about additional functionality for developers.
 

.. toctree::
   :maxdepth: 1

   introduction
   getting_started
   core_concepts
   importing_data
   using_coop
   how_to_guides
   examples
   developers


.. image:: https://colab.research.google.com/assets/colab-badge.svg
   :target: https://colab.research.google.com/github/expectedparrot/edsl/blob/main/examples/create_agents.ipynb 
   :alt: Open In Colab
   :hidden:

..
   Indices and tables
   ==================

   * :ref:`genindex`
   * :ref:`modindex`
   * :ref:`search`

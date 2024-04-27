.. _index:

EDSL Docs
=========

This page contains documentation, tutorials and demo notebooks for the <b><i>Expected Parrot Domain-Specific Language</i></b> (EDSL) library, an open-source Python package for conducting AI-powered research. 
The contents are organized into the following sections:

Introduction
------------
- :ref:`overview`:  An overview of the purpose, concepts and goals of the EDSL package.
- :ref:`whitepaper`:  A whitepaper about the EDSL package.
- :ref:`citation`:  Instructions on how to cite the package in your work.

Getting Started
---------------
- :ref:`starter_tutorial`:  A tutorial to help you get started using the package.
- :ref:`installation`:  Instructions for installing the EDSL package.
- :ref:`api_keys`:  Instructions for obtaining and storing API keys for language models.

Core Concepts
-------------
- :ref:`questions`:  Learn about the different types of questions and their applications.
- :ref:`scenarios`:  Explore how questions can be dynamically parameterized for tasks like data labeling.
- :ref:`surveys`:  Discover how to construct surveys and implement survey rules and conditions.
- :ref:`agents`:  Understand the design and implementation of AI agents that respond to surveys.
- :ref:`language_models`:  Examine the selection and application of language models for generating results.
- :ref:`results`:  Investigate methods for analyzing and utilizing survey results.

How-to Guides
-------------
Examples of special methods and use cases, such as data labeling tasks, cognitive testing, dynamic agent traits and creating new methods.

Notebooks
---------
A variety of templates and examples for using the package to conduct different kinds of research.
*We're happy to create a new notebook for your use case!*

Links
-----
.. raw:: html

   <b><a href="https://pypi.org/project/edsl" target="_blank">PyPI:</a></b> Download the latest version of EDSL at PyPI.     

   <br><br>

   <b><a href="https://github.com/expectedparrot/edsl" target="_blank">GitHub:</a></b> Get the latest EDSL updates at GitHub.

   <br><br>

   <b><a href="https://discord.com/invite/mxAYkjfy9m" target="_blank">Discord:</a></b> Join our Discord channel to ask questions and connect with other users.

   <br><br>

   <b>Contact:</b> Send us an email at info@expectedparrot.com






.. toctree::
   :maxdepth: 2
   :caption: Introduction
   :hidden:

   overview
   whitepaper
   citation

.. toctree::
   :maxdepth: 2
   :caption: Getting Started
   :hidden:

   starter_tutorial
   installation
   api_keys

.. toctree::
   :maxdepth: 2
   :caption: Core Concepts
   :hidden:

   questions
   scenarios
   surveys
   agents
   prompts
   language_models
   results

.. toctree::
   :maxdepth: 2
   :caption: How-to Guides
   :hidden:

   notebooks/edsl_components
   notebooks/export_survey_updates.ipynb
   notebooks/question_extract_example
   notebooks/data_labeling_example.ipynb
   notebooks/example_agent_dynamic_traits.ipynb
   notebooks/research_methods

.. toctree::
   :maxdepth: 2
   :caption: Notebooks
   :hidden:

   notebooks/data_labeling_agent.ipynb
   notebooks/explore_llm_biases.ipynb
   notebooks/research_random_silicon_sampling
   notebooks/explore_survey_contexts
   notebooks/free_responses
   notebooks/qualitative_research
   notebooks/digital_twin
   notebooks/grading_experiment

.. toctree::
   :maxdepth: 2
   :caption: Developers
   :hidden:

   data
   enums

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



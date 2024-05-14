.. _index:

EDSL: AI-Powered Research
=========================

*Expected Parrot Domain-Specific Language* (EDSL) is an open-source Python package for conducting AI-powered research.
   
.. raw:: html

   EDSL is developed by <a href="https://www.expectedparrot.com" target="_blank">Expected Parrot</a> and available under the MIT License.
   <br><br>

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


This page provides documentation, tutorials and demo notebooks for the EDSL package.
The contents are organized into several key sections to help you get started using it:

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

Developers
----------
Information about additional functionality for developers.


.. Links
.. -----
.. *Updates*

.. .. raw:: html

..    <a href="https://pypi.org/project/edsl" target="_blank"><i class="fab fa-python"></i></a>&nbsp;&nbsp;Download the latest version of EDSL at <a href="https://pypi.org/project/edsl" target="_blank">PyPI</a>.     
..    <br><br>

..    <a href="https://github.com/expectedparrot/edsl" target="_blank"><i class="fab fa-github"></i></a>&nbsp;&nbsp;Get the latest EDSL updates at <a href="https://github.com/expectedparrot/edsl" target="_blank">GitHub</a>.
..    <br><br>

.. *Community*

.. .. raw:: html

..    <a href="https://discord.com/invite/mxAYkjfy9m" target="_blank"><i class="fab fa-discord"></i></a>&nbsp;&nbsp;Join our <a href="https://discord.com/invite/mxAYkjfy9m" target="_blank">Discord</a> channel to connect with other users and ask questions.
..    <br><br>

.. *Support*

.. .. raw:: html

..    <i class="far fa-envelope"></i>&nbsp;&nbsp;Send us an email at <b>info@expectedparrot.com</b>.    
..    <br><br>

 


.. toctree::
   :maxdepth: 2
   :caption: Introduction
   :hidden:

   overview
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
   data
   exceptions

.. toctree::
   :maxdepth: 2
   :caption: How-to Guides
   :hidden:

   notebooks/edsl_components.ipynb
   notebooks/export_survey_updates.ipynb
   notebooks/question_extract_example.ipynb
   notebooks/data_labeling_example.ipynb
   notebooks/example_agent_dynamic_traits.ipynb
   notebooks/research_methods.ipynb

.. toctree::
   :maxdepth: 2
   :caption: Notebooks
   :hidden:

   notebooks/data_labeling_agent.ipynb
   notebooks/random_numbers.ipynb
   notebooks/concept_induction.ipynb
   notebooks/testing_training_data.ipynb
   notebooks/analyze_evaluations.ipynb
   notebooks/explore_llm_biases.ipynb
   notebooks/research_random_silicon_sampling.ipynb
   notebooks/explore_survey_contexts.ipynb
   notebooks/free_responses.ipynb
   notebooks/qualitative_research.ipynb
   notebooks/digital_twin.ipynb
   notebooks/grading_experiment.ipynb

.. toctree::
   :maxdepth: 2
   :caption: Developers
   :hidden:

   enums
   jobs 
   interviews
   answers
   contributing

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



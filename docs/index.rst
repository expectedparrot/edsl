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
- :ref:`remote_inference`: Run your jobs on our server. 

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

<<<<<<< HEAD
=======
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
   token_limits

.. toctree::
   :maxdepth: 2
   :caption: Importing Data
   :hidden:

   conjure

.. toctree::
   :maxdepth: 2
   :caption: Coop
   :hidden:

   coop
   notebooks
   remote_caching
   remote_inference

.. toctree::
   :maxdepth: 2
   :caption: How-to Guides
   :hidden:

   notebooks/data_labeling_example.ipynb
   notebooks/cheatsheet_scenarios.ipynb
   notebooks/scenario_from_pdf.ipynb
   notebooks/batching_results.ipynb
   notebooks/adding_metadata.ipynb
   notebooks/survey_memories.ipynb
   notebooks/example_agent_dynamic_traits.ipynb
   notebooks/research_methods.ipynb
   notebooks/edsl_components.ipynb
   notebooks/export_survey_updates.ipynb
   notebooks/question_extract_example.ipynb
   notebooks/data_cleaning.ipynb

.. toctree::
   :maxdepth: 2
   :caption: Notebooks
   :hidden:

   notebooks/agentifying_responses.ipynb
   notebooks/summarizing_transcripts.ipynb
   notebooks/data_labeling_agent.ipynb
   notebooks/conduct_interview.ipynb
   notebooks/qualitative_research.ipynb
   notebooks/random_numbers.ipynb
   notebooks/model_walkoff.ipynb
   notebooks/concept_induction.ipynb
   notebooks/testing_training_data.ipynb
   notebooks/comparing_model_responses.ipynb
   notebooks/analyze_evaluations.ipynb
   notebooks/evaluating_job_posts.ipynb
   notebooks/explore_llm_biases.ipynb
   notebooks/research_random_silicon_sampling.ipynb
   notebooks/explore_survey_contexts.ipynb
   notebooks/free_responses.ipynb
   notebooks/digital_twin.ipynb
   notebooks/river_problem.ipynb
   notebooks/writing_style.ipynb

.. toctree::
   :maxdepth: 2
   :caption: Developers
   :hidden:

   contributing
   interview
   jobs 
   interviews
   answers
   enums
>>>>>>> f82452ce622aaceeb341632d935f20d4136b3f43

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

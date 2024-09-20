.. _index:

EDSL: AI-Powered Research
=========================

*Expected Parrot Domain-Specific Language* (EDSL) is an open-source Python package for conducting AI-powered research.
   
EDSL is developed by `Expected Parrot <https://www.expectedparrot.com>`_ and available under the MIT License.

This page provides documentation, tutorials and demo notebooks for the EDSL package and the `Coop <https://www.expectedparrot.com/explore>`_: a platform for creating, storing and sharing AI research. 
The contents are organized into key sections to help you get started:


Links
-----

- Download the current version of EDSL at `PyPI <https://pypi.org/project/edsl>`_.

- Get the latest EDSL updates at `GitHub <https://github.com/expectedparrot/edsl>`_.

- Create a `Coop account <https://www.expectedparrot.com/login>`_.

- Join our `Discord channel <https://discord.com/invite/mxAYkjfy9m>`_.

- Follow us on social media:

  - `Twitter/X <https://twitter.com/expectedparrot>`_

  - `LinkedIn <https://www.linkedin.com/company/expectedparrot>`_
  
  - `Blog <https://blog.expectedparrot.com>`_
  

Introduction
------------

- :ref:`overview`: An overview of the purpose, concepts and goals of the EDSL package.
- :ref:`whitepaper`: A whitepaper about the EDSL package (*in progress*).
- :ref:`citation`: How to cite the package in your work.


Technical Setup
---------------

- :ref:`installation`: Instructions for installing the EDSL package.
- Create a :ref:`coop` to create, store and share content on the Expected Parrot server. 
- :ref:`api_keys`: (*Optional*) Instructions for storing API keys for language models to use EDSL locally.

Getting Started
---------------

- :ref:`starter_tutorial`: A tutorial to help you get started using EDSL.

Core Concepts
-------------

- :ref:`questions`: Learn about different question types and applications.
- :ref:`scenarios`: Explore how questions can be dynamically parameterized for tasks like data labeling.
- :ref:`surveys`: Construct surveys and implement rules and conditions.
- :ref:`agents`: Design and implement AI agents to respond to surveys.
- :ref:`language_models`: Select language models to generate results.

Working with Results
--------------------

- :ref:`results`: Access built-in methods for analyzing and utilizing survey results as datasets.
- :ref:`caching`: Learn about caching and sharing results.
- :ref:`exceptions`: Identify and handle exceptions in your survey design.
- :ref:`token_usage`: Manage token limits for language models, and monitor and reduce token usage as desired.

Coop 
----

Coop is a platform for creating, storing and sharing EDSL content and AI research.

- :ref:`coop`: Learn how to create, store and share content at the Coop. 
- :ref:`remote_caching`: Use remote caching to automatically store survey results and API calls on the Expected Parrot server. 
- :ref:`remote_inference`: Use remote inference to run jobs on the Expected Parrot server. 
- :ref:`notebooks`: Instructions for sharing `.ipynb` files with other users at the Coop. 

Importing Data
--------------

- :ref:`conjure`: Automatically import other survey data into EDSL to:
  
  * Clean and analyze your data
  * Create AI agents for respondents and conduct follow-on interviews
  * Extend your results with new questions and surveys
  * Store and share your data on the Coop

How-to Guides
-------------

Examples of special methods and use cases for EDSL, including:

* Data labeling, cleaning and analysis
* Cognitive testing
* Dynamic agent traits
* Creating new methods

Notebooks
---------

Templates and example code for using EDSL to conduct different kinds of research.
*We're happy to create a new notebook for your use case!*

Developers
----------

Information about additional functionality for developers.
 

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

.. toctree::
   :maxdepth: 2
   :caption: Working with Results
   :hidden:

   results
   data
   exceptions
   token_usage

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
   :caption: Importing Data
   :hidden:

   conjure

.. toctree::
   :maxdepth: 2
   :caption: How-to Guides
   :hidden:

   notebooks/edsl_intro.ipynb
   notebooks/data_labeling_example.ipynb
   notebooks/image_scenario_example.ipynb
   notebooks/question_loop_scenario.ipynb
   notebooks/scenario_list_wikipedia.ipynb
   notebooks/scenario_from_pdf.ipynb
   notebooks/batching_results.ipynb
   notebooks/adding_metadata.ipynb
   notebooks/example_agent_dynamic_traits.ipynb
   notebooks/research_methods.ipynb
   notebooks/edsl_components.ipynb
   notebooks/question_extract_example.ipynb
   notebooks/data_cleaning.ipynb

.. toctree::
   :maxdepth: 2
   :caption: Notebooks
   :hidden:

   notebooks/next_token_probs.ipynb
   notebooks/scenariolist_unpivot.ipynb
   notebooks/nps_survey.ipynb
   notebooks/agentifying_responses.ipynb
   notebooks/summarizing_transcripts.ipynb
   notebooks/data_labeling_agent.ipynb
   notebooks/conduct_interview.ipynb
   notebooks/qualitative_research.ipynb
   notebooks/random_numbers.ipynb
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
   notebooks/writing_style.ipynb
   notebooks/google_form_to_edsl.ipynb
   notebooks/edsl_polling.ipynb
   notebooks/ces_data_edsl.ipynb

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

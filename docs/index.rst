.. _index:

EDSL: AI-Powered Research
=========================

*Expected Parrot Domain-Specific Language* (EDSL) is an `open-source Python package <https://github.com/expectedparrot/edsl>`_ for conducting AI-powered research.
   
EDSL is developed by `Expected Parrot <https://www.expectedparrot.com>`_ and available under the MIT License.

This page provides documentation, tutorials and demo notebooks for the EDSL package and the `Coop <https://www.expectedparrot.com/explore>`_: a platform for creating, storing and sharing AI research. 
The contents are organized into key sections to help you get started.


Researchers
-----------

**Are you using EDSL for a research project? We'd love to hear about your experience!**

Send us an email at info@expectedparrot.com and we'll provide credits to run your project or a gift card for your time.


Links
-----

- Download the current version of EDSL at `PyPI <https://pypi.org/project/edsl>`_.
- Get the latest EDSL updates at `GitHub <https://github.com/expectedparrot/edsl>`_.
- Create a `Coop account <https://www.expectedparrot.com/login>`_ to store and share your research and access special features, including:
  
  * :ref:`survey_builder`: An interface for launching hybrid human-AI surveys
  * :ref:`remote_inference`: Run surveys on the Expected Parrot server
  * :ref:`remote_caching`: Automatically store results and API calls on the Expected Parrot server
  * :ref:`filestore`: Store and share data files for use in EDSL projects

- Explore research at the `Coop <https://www.expectedparrot.com/explore>`_.
- Join the `Discord channel <https://discord.com/invite/mxAYkjfy9m>`_.
- Follow on social media: `Twitter/X <https://twitter.com/expectedparrot>`_, `LinkedIn <https://www.linkedin.com/company/expectedparrot>`_, `Blog <https://blog.expectedparrot.com>`_
  

Introduction
------------

- :ref:`overview`: An overview of the purpose, concepts and goals of the EDSL package.
- :ref:`whitepaper`: A whitepaper about the EDSL package (*in progress*).
- :ref:`citation`: How to cite the package in your work.
- :ref:`papers`: Research papers and articles that use or cite EDSL.


Technical Setup
---------------

- :ref:`installation`: Instructions for installing the EDSL package.
- :ref:`coop`: Create, store and share research on the Expected Parrot server. 
- :ref:`api_keys`: Instructions for storing API keys to use EDSL locally (*optional*).


Getting Started
---------------

- :ref:`starter_tutorial`: A tutorial to help you get started using EDSL.


Core Concepts
-------------

- :ref:`questions`: Learn about different question types and applications.
- :ref:`scenarios`: Explore how questions can be dynamically parameterized for tasks like data labeling.
- :ref:`surveys`: Construct surveys with rules and conditions.
- :ref:`agents`: Design AI agents with relevant traits to respond to surveys.
- :ref:`language_models`: Select language models to generate results.


Working with Results
--------------------

- :ref:`results`: Access built-in methods for analyzing survey results as datasets.
- :ref:`caching`: Learn about caching and sharing results.
- :ref:`exceptions`: Identify and handle exceptions in running surveys.
- :ref:`token_usage`: Monitor token limits and usage for language models.


Coop 
----

Coop is a platform for creating, storing and sharing EDSL content and AI-based research.

- :ref:`coop`: Learn how to create, store and share content at the Coop. 
- :ref:`survey_builder`: An interface for launching hybrid human-AI surveys.
- :ref:`filestore`: Store and share files for use in EDSL projects.
- :ref:`remote_inference`: Run surveys on the Expected Parrot server. 
- :ref:`remote_caching`: Automatically store survey results and API calls on the Expected Parrot server. 
- :ref:`notebooks`: Instructions for posting `.ipynb` files to the Coop. 


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

- Data labeling
- Data cleaning
- Analyzing survey results 
- Adding data to surveys from CSVs, PDFs, images and other sources
- Conducting agent conversations
- Converting surveys into EDSL
- Cognitive testing 


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
   whitepaper
   citation
   papers

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
   remote_inference
   remote_caching
   filestore

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
   notebooks/data_cleaning.ipynb
   notebooks/scenario_from_pdf.ipynb
   notebooks/image_scenario_example.ipynb
   notebooks/scenario_list_wikipedia.ipynb
   notebooks/scenarios_filestore_example.ipynb
   notebooks/adding_metadata.ipynb
   notebooks/question_loop_scenarios.ipynb
   notebooks/example_agent_dynamic_traits.ipynb
   notebooks/agentifying_responses.ipynb
   notebooks/batching_results.ipynb
   notebooks/research_methods.ipynb

.. toctree::
   :maxdepth: 2
   :caption: Notebooks
   :hidden:

   notebooks/next_token_probs.ipynb
   notebooks/summarizing_transcripts.ipynb
   notebooks/analyze_evaluations.ipynb
   notebooks/concept_induction.ipynb
   notebooks/conduct_interview.ipynb
   notebooks/qualitative_research.ipynb
   notebooks/nps_survey.ipynb
   notebooks/data_labeling_agent.ipynb
   notebooks/scenariolist_unpivot.ipynb
   notebooks/random_numbers.ipynb
   notebooks/testing_training_data.ipynb
   notebooks/comparing_model_responses.ipynb
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

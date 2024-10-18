.. _index:

EDSL: AI-Powered Research
=========================

*Expected Parrot Domain-Specific Language* (EDSL) is an open-source Python package (`GitHub <https://github.com/expectedparrot/edsl>`_) for conducting AI-powered research.
   
EDSL is developed by `Expected Parrot <https://www.expectedparrot.com>`_ and available under the MIT License.

This page provides documentation, tutorials and demo notebooks for the EDSL package and `Coop <https://www.expectedparrot.com/content/explore>`_: a platform for creating, storing and sharing AI-based research. 
The contents are organized into key sections to help you get started.


Researchers
-----------

Are you using EDSL for a research project?
Email us at info@expectedparrot.com and we'll give you free credits to run your project.


Getting started 
---------------

Steps for getting started using the EDSL package: 

1. Download the EDSL package. See :ref:`installation` instructions.
2. *(Optional)*  Create a `Coop account <https://www.expectedparrot.com/login>`_ to store and share research.
3. Decide how you want to use EDSL: 

   *To run surveys on the Expected Parrot server with available models:*
   Activate :ref:`remote_inference` from your `Coop API Settings <https://www.expectedparrot.com/home/api>`_ page.
   Copy and store your Expected Parrot API key.
   
   *To run surveys locally:*
   Copy and store your own :ref:`api_keys` for language models.

   We recommend storing your API keys in a *.env* file in your working directory. 
   See instructions in the :ref:`api_keys` section.

4. Explore a :ref:`starter_tutorial` and other how-to guides and notebooks for examples.


Support
-------

- Send us an email: info@expectedparrot.com
- Join the `Discord channel <https://discord.com/invite/mxAYkjfy9m>`_
- Follow on social media: `Twitter/X <https://twitter.com/expectedparrot>`_, `LinkedIn <https://www.linkedin.com/company/expectedparrot>`_, `Blog <https://blog.expectedparrot.com>`_
 

Introduction
------------

- :ref:`overview`: An overview of the purpose, concepts and goals of the EDSL package.
- :ref:`whitepaper`: A whitepaper about the EDSL package (*in progress*).
- :ref:`citation`: How to cite the package in your work.
- :ref:`papers`: Research papers and articles that use or cite EDSL.


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

`Coop <https://docs.expectedparrot.com/en/latest/coop.html>`_ is a platform for AI-based research.
`Create an account <https://www.expectedparrot.com/login>`_ to store and share your work and get access to special features, including: 

- :ref:`remote_inference`: Run surveys with any available models on the Expected Parrot server. 
- :ref:`remote_caching`: Automatically store results and API calls on the Expected Parrot server. 
- :ref:`survey_builder`: Design and launch hybrid human-AI surveys.
- :ref:`notebooks`: Post `.ipynb` files to the Coop. 
- :ref:`filestore`: Store and share data files for use in EDSL projects.


Importing Surveys
-----------------

- :ref:`conjure`: Automatically import other survey data into EDSL to:
  
  * Clean and analyze your data
  * Create AI agents and conduct follow-on interviews
  * Extend results with new questions
  * Store and share data at the Coop


How-to Guides & Notebooks
-------------------------

Examples of special methods and use cases for EDSL, including:

- Data labeling
- Data cleaning
- Analyzing survey results 
- Adding data to surveys from CSVs, PDFs, images and other sources
- Conducting agent conversations
- Converting surveys into EDSL
- Cognitive testing 
- Research methods

 
Links
-----

- Download the current version of EDSL at `PyPI <https://pypi.org/project/edsl>`_.
- Get the latest EDSL updates at `GitHub <https://github.com/expectedparrot/edsl>`_.
- Create a `Coop account <https://www.expectedparrot.com/login>`_.
- Join the `Discord channel <https://discord.com/invite/mxAYkjfy9m>`_.
- Follow on social media: `Twitter/X <https://twitter.com/expectedparrot>`_, `LinkedIn <https://www.linkedin.com/company/expectedparrot>`_, `Blog <https://blog.expectedparrot.com>`_


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
   notebooks/yoga_studio_name_survey.ipynb
   notebooks/scenario_from_pdf.ipynb
   notebooks/image_scenario_example.ipynb
   notebooks/scenario_list_wikipedia.ipynb
   notebooks/scenarios_filestore_example.ipynb
   notebooks/adding_metadata.ipynb
   notebooks/question_loop_scenarios.ipynb
   notebooks/example_agent_dynamic_traits.ipynb
   notebooks/import_agents.ipynb
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

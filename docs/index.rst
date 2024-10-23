.. _index:

Expected Parrot: Tools for AI-Powered Research
==============================================

This page provides documentation for *Expected Parrot Domain-Specific Language* (EDSL), a Python package for conducting research with AI agents and large language models.
It also provides information about key features and integrated applications, including:

| **Streamlined access to language models**
| Get an Expected Parrot API key to conduct research with hundreds of popular models at once. `Learn more <https://docs.expectedparrot.com/en/latest/remote_inference.html>`_.

| **Collaboration platform**
| Create, store and share research and projects from anywhere at `Coop <https://www.expectedparrot.com/content/explore>`_.

| **Working with AI agents**
| Features for designing agent personas from many sources. `Learn more <https://docs.expectedparrot.com/en/latest/notebooks/import_agents.html>`_.

| **Importing data**
| Features for integrating and analyzing data from many sources. `Learn more <https://docs.expectedparrot.com/en/latest/scenarios.html>`_.

| **Hybrid human-AI surveys**
| Launch hybrid surveys and combine responses from humans and AI. `Learn more <https://docs.expectedparrot.com/en/latest/survey_builder.html>`_.


Use cases 
---------

EDSL and its integrated applications are designed to make it easy to conduct research with surveys and experiments and to analyze responses -- from humans or AI.
Common use cases include:

| **Data labeling and cleaning** 
| Design a data labeling or cleaning task as questions about your data, and then use language models to generate responses in a formatted dataset. See `examples <https://docs.expectedparrot.com/en/latest/notebooks/data_labeling_example.html>`_.

| **Market research** 
| Administer surveys to gather insights about consumer preferences, behaviors, and trends. Use AI agents to simulate customer personas and analyze their responses. See `examples <>`_.

| **User experience** 
| Conduct user experience research by designing surveys that assess user satisfaction, usability, and engagement. Use AI agents to simulate user profiles and analyze their feedback on products or services. See `examples <https://docs.expectedparrot.com/en/latest/notebooks/nps_survey.html>`_.

| **Integrate human and AI data**
| Combine human responses with AI-generated responses to create richer datasets. See `examples <>`_.

| **Analyze survey data**
| Import survey data from other sources (SPSS, CSV), analyze it using EDSL's built-in methods, and simulate follow-up surveys or interviews using AI agents. See `examples <https://docs.expectedparrot.com/en/latest/conjure.html>`_.

| **Social science research**
| Conduct academic research by designing surveys that explore specific hypotheses or research questions. Use AI agents to gather qualitative or quantitative data and analyze the results. See `examples <>`_.

Learn more about purposes and key features of EDSL in the :ref:`overview` section.


Getting started 
---------------

| **1. Install EDSL**
| Download the EDSL package. See :ref:`installation` instructions.

| **2. Create a Coop account**
| Create a `Coop account <https://www.expectedparrot.com/login>`_ to store and share your research projects.

| **3. Choose how to access language models**
| Decide how you want to use models: 

| *Choose from any available models at the Expected Parrot server:*
| Activate :ref:`remote_inference` at your Coop account and store your Expected Parrot API key.

*or*

| *Use models your own:*
| Store your own :ref:`api_keys` for language models that you want to use locally.

| **4. Explore examples**
| Explore a :ref:`starter_tutorial` and other how-to guides and notebooks.


Researchers
-----------

Are you using EDSL for a research project?
Send an email to *info@expectedparrot.com* and we'll give you free credits to run your project!


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
- Send an email: *info@expectedparrot.com*


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
   notebooks/skip_logic_scenarios.ipynb
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

.. _index:

Expected Parrot: Tools for AI-Powered Research
==============================================

Welcome to the documentation for the *Expected Parrot Domain-Specific Language* (EDSL), a Python package for conducting research with AI agents and large language models.
This guide also highlights key features and integrated applications:

* **Access to hundreds of models:** A single API key lets you conduct research with many popular models at once. `Learn more <https://docs.expectedparrot.com/en/latest/remote_inference.html>`_.
* **Collaboration made easy:** Use `Coop <https://www.expectedparrot.com/content/explore>`_ to create, store, and share your research projects seamlessly.
* **Data integrations:** Easily import and analyze data from various sources. `Learn more <https://docs.expectedparrot.com/en/latest/scenarios.html>`_.
* **Hybrid human-AI surveys:** Launch surveys and collect responses from both humans and AI agents. `Learn more <https://docs.expectedparrot.com/en/latest/survey_builder.html>`_.
* **Built-in analysis tools:** Analyze survey results with EDSL's built-in methods. `Learn more <https://docs.expectedparrot.com/en/latest/results.html>`_.

Use cases 
---------

EDSL and its integrated applications are designed to simplify survey creation, experiment execution, and response analysis—whether from humans or AI. 
Common use cases include:

| **Data labeling and cleaning** 
| Design tasks that involve labeling or cleaning data through questionsa, and then use language models to generate responses in formatted datasets. See `examples <https://docs.expectedparrot.com/en/latest/notebooks/data_labeling_example.html>`_.

| **Market research** 
| Administer surveys to gather insights on consumer preferences, behaviors, and trends. Simulate customer personas with AI agents and analyze their responses. See `examples <file:///Users/a16174/edsl/.temp/docs/notebooks/yoga_studio_name_survey.html>`_.

| **User experience research** 
| Design surveys to assess user satisfaction, usability, and engagement. Use AI agents to simulate user profiles and analyze their feedback on products or services. See `examples <https://docs.expectedparrot.com/en/latest/notebooks/nps_survey.html>`_.

| **Integrate human and AI data**
| Combine human responses with AI-generated responses to create richer datasets. See `examples <file:///Users/a16174/edsl/.temp/docs/notebooks/import_agents.html>`_.

| **Analyze survey data**
| Import survey data from various sources (SPSS, CSV), analyze it using EDSL's built-in tools. Simulate follow-up surveys and interviews using AI agents. See `examples <https://docs.expectedparrot.com/en/latest/conjure.html>`_.

| **Social science research**
| Design surveys to explore hypotheses and gather qualitative or quantitative data using AI agents. 

For more on EDSL's key features and use cases, visit the :ref:`overview` section.


Getting started 
---------------

| **1. Install EDSL**
| Download and install the EDSL package. :ref:`installation` instructions.

| **2. Create a Coop account**
| `Sign up <https://www.expectedparrot.com/login>`_ for an account to store and share your research projects.

| **3. Choose your model access methods**
| You can either access language models remotely through the Expected Parrot server or use your own API keys to access models locally. 

| ***For remote access to all available models:***
| Activate :ref:`remote_inference` via your Coop account and store your Expected Parrot API key.

| ***For local access to specific models:***
| Store your own :ref:`api_keys` for the language models that you wish to use.

| **4. Explore examples**
| Get started with our :ref:`starter_tutorial` and explore additional guides and notebooks.


Researchers
-----------

Are you using EDSL for a research project?
Send an email to *info@expectedparrot.com* and we'll give you credits to run your project!


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

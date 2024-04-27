.. _overview:

Overview
========

What is EDSL? 
-------------

*Expected Parrot Domain-Specific Language* (EDSL) is an open-source Python package for conducting AI-powered research. 
EDSL simplifies the creation and execution of surveys, experiments, data labeling tasks, and other research activities involving large numbers of AI agents and language models. 
Its primary goal is to facilitate complex AI-based research tasks with ease and efficiency.

Why EDSL?
---------
Most new software for large language models (LLMs) focuses on tools for constructing agents and real-time systems, such as chatbots. 
Less attention is being paid to efficiently managing large-scale tasks such as survey responses or data labeling that involve varying agent behaviors and model parameters. 
These tasks often include intricate dependencies, such as agent memory or conditional logic, which complicates execution. 
EDSL addresses this gap by offering robust tools for designing, executing, and managing data-intensive tasks using LLMs, particularly in social science research.

Initially developed for our internal research needs, EDSL quickly proved invaluable for broader applications within this domain. 
Recognizing the limitations of procedural coding (looping through agents, questions, and models), we shifted towards a declarative domain-specific language. 
This approach enhances expressiveness, allowing users to achieve more with minimal code.

Key concepts
------------
At its core, EDSL revolves around the notion of a `Question` answered by an AI `Agent` using a large language `Model`, producing a `Result`. 
These results can be analyzed, visualized, shared, or further utilized to refine subsequent questions. 
EDSL supports various question types, from free text to multiple choice, that can be grouped into a `Survey` that operates either in parallel or based on specific rules and conditional logic. 

Questions may also be parameterized with a `Scenario` to provide contextual data or variations, facilitating the administration of multiple question versions simultaneously. 
This functionality is particularly beneficial for data labeling tasks, where each dataset item is queried to generate annotated data. 

Surveys in EDSL can be executed with multiple agents and models concurrently, offering diverse and rich response types, essential for robust data analysis and application.

Key components
--------------
These concepts form the basic classes of the package, and are described in detail in the following sections:

:ref:`questions`: A `Question` serves as the foundational element for research design in EDSL. 
It allows users to choose from various question types, such as free text or multiple choice, depending on the desired outcome of the results.

:ref:`surveys`: A `Survey` aggregates multiple questions, which can be administered either simultaneously or according to predefined rules. 
Surveys are versatile, supporting different agents and models to yield varied responses. 
They can also incorporate diverse "scenarios" that supply context and data, enhancing the depth and relevance of the questions posed.

:ref:`agents`: An `Agent` represents an AI entity programmed to respond to the survey questions. 
Each agent can possess unique traits that influence their responses, including their background, expertise, or memory of previous interactions within the survey.

:ref:`language_models`: A `Model` refers to a large language model that generates answers to the questions. 
EDSL is designed to be model-agnostic, enabling the integration of multiple models to facilitate response comparison and selection.

:ref:`scenarios`: A `Scenario` provides specific context or data to a question at the time of its execution. 
This feature allows for dynamic parameterization of questions, enabling the same question to be adapted and asked across varied contexts efficiently.

:ref:`results`: A `Result` is the direct output obtained from executing a question. 
These results can be analyzed, visualized, shared, and utilized to refine further inquiries or enhance the structure of subsequent surveys.

The following illustrations provide a visual representation of how these components interact:


1. Construct questions of various types:

.. image:: static/survey_graphic1.png
   :alt: Construct questions
   :align: center



2. Parameterize questions with content or data:

.. image:: static/survey_graphic2.png
   :alt: Optionally parameterize questions
   :align: center



3. Create AI agents to answer the questions:

.. image:: static/survey_graphic3.png
   :alt: Create AI agents to answer the questions
   :align: center



4. Select AI models to generate results:

.. image:: static/survey_graphic4.png
   :alt: Select AI models to simulate results
   :align: center



Key operations
--------------
*Running a Survey*

The core operation within EDSL involves administering a survey to one or more agents using specific models. 
This is executed by invoking the `run()` method on a `Survey` object, which must first be configured with any desired `Agent`, `Model`, and `Scenario` objects using the `by()` method. 
This method chain ensures that each question within the survey is presented to each agent, responses are generated using each model, and a `Result` object is returned for every unique question-agent-model combination. 

The operation is typically structured as follows:

.. code-block:: python

   results = survey.by(scenarios).by(agents).by(models).run()


Key features 
------------
*Python Integration*


EDSL leverages Python's robust ecosystem, seamlessly integrating with existing Python tools. 
It is ideally used within a notebook environment, facilitating the execution and detailed analysis of research outcomes. 
Key features include:

*Built-in Analytical Tools*: Methods for data analysis and result visualization are built into EDSL, with the capability to expand these tools with custom methods tailored to specific research needs.

*Model Agnosticism*: The framework's design allows for the application of diverse language models and agents to the same set of questions, enabling comparative analysis across different models.

*Open Source Flexibility*: EDSL is open-source under a permissive license, offering the freedom to use, modify, and extend it for personal or commercial projects.


Coop: Collaborative Research Platform
-------------------------------------
*(Coming soon!)*

*Enhancing Research Collaboration*: EDSL promotes not only the creation of research but also the sharing of insights, code, and results. 
`Coop` is a platform designed to enhance collaborative research efforts. 
It functions similarly to how GitHub operates with Git, providing essential services such as:

*Automatic Caching and Versioning*: Ensures that all aspects of your research are tracked and retrievable.

*Effortless Sharing*: Facilitates the sharing of code, data, and results, streamlining collaborative efforts.


Use cases
---------
EDSL is adept at handling a broad spectrum of research tasks that benefit from the integration of AI agents and language models. 
Potential applications include:

*Survey Simulation and Experimental Research*: Create and simulate detailed surveys and experiments.

*Data Labeling and Classification*: Efficiently label and classify large datasets.

*Data Augmentation*: Enhance datasets by generating synthetic, yet realistic, data additions.

*Synthetic Data Generation*: Produce completely new data sets that mimic real-world data for training and testing models.


Getting help 
------------
EDSL objects have built-in help methods that provide information on their attributes and methods:

.. code-block:: python

   help(object)
   
   object.example()

For example, to see an example of a multiple choice question, you can run:

.. code-block:: python

   QuestionMultipleChoice.example()


Please also see the notebooks listed here for help getting started and example code for applications and research ideas.


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




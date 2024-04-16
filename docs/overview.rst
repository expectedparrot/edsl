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
These concepts are the basic classes of the package, and are described in detail in the following sections:

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

The running of a job--administering a survey to an agent and model--is the central operation in EDSL. 
It is initiated by calling the `run()` method on a survey object after it has been configured with agents, models and scenarios with the `by()` method.
This operation delivers each question to each of the agents, generates a response using each of the specified models, and returns a result object for each question/agent/model combination.
This operation takes the following general form:

.. code-block:: python

    results = survey.by(scenarios).by(agents).by(models).run()


Key features 
------------
EDSL is python-based and plays nicely with existing python tooling.
It is designed to be used in a notebook context, where you can easily run and analyze the results of your research.
It has built-in methods for analysis and visualization of results, and can be readily extended with custom methods.
It is also model agnostic, so you can easily present the same questions to different models and agents in parallel to compare results.
It is open source with a permissive license, so you can use it for your own research or build on it for your own projects.

Coop
----
*Coming soon!*

EDSL is designed to facilitate sharing of research, code and results. 

 `Coop`_ is a platform for sharing and collaborating on research projects, and is built around the EDSL package.

 Coop provides automatic caching, versioning and sharing of code, data and results, and it designed to work with EDSL the way that GitHub works with git.

Use cases
---------
EDSL is designed for a wide range of research tasks that involve--or *could* benefit from or be extended by the use of--AI agents and language models, including:

* Simulating surveys and experiments
* Data labeling and classification
* Data augmentation
* Synthetic data generation

.. raw:: html

   Some ideas for using EDSL are explored in our <a href="https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Tutorial%20-%20Starter%20Tutorial-e080f5883d764931960d3920782baf34" target="_blank">example interactive notebooks</a>.

Getting help 
------------
EDSL objects have built-in help methods that provide information on their attributes and methods:

.. code-block:: python

   help(object)
   
   object.example()

For example, to see an example of a multiple choice question, you can run:

.. code-block:: python

   QuestionMultipleChoice.example()


Links
-----
.. raw:: html

   Download the latest version of EDSL at PyPI: <a href="https://pypi.org/project/edsl" target="_blank">https://pypi.org/project/edsl/</a>     
   <br><br>
   Get the latest updates at GitHub: <a href="https://github.com/expectedparrot/edsl" target="_blank">https://github.com/expectedparrot/edsl</a>
   <br><br>
   Access sample code and research examples: 
   <br>
   * <a href="http://www.expectedparrot.com/getting-started#edsl-showcase" target="_blank">EDSL Showcase</a>
   <br>
   * <a href="https://deepnote.com/workspace/expected-parrot-c2fa2435-01e3-451d-ba12-9c36b3b87ad9/project/Expected-Parrot-examples-b457490b-fc5d-45e1-82a5-a66e1738a4b9/notebook/Tutorial%20-%20Starter%20Tutorial-e080f5883d764931960d3920782baf34" target="_blank">Notebooks</a>
   <br><br>
   Join our Discord to connect with other users! <a href="https://discord.com/invite/mxAYkjfy9m" target="_blank">https://discord.com/invite/mxAYkjfy9m</a>
   <br><br>
   Contact us for support: info@expectedparrot.com
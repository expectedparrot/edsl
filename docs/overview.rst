.. _overview:

Overview
========

What is EDSL? 
-------------

*Expected Parrot Domain-Specific Language* (EDSL) is an open-source Python package for conducting AI-powered research. 
EDSL simplifies the creation and execution of surveys, experiments, data labeling tasks, and other research activities involving large numbers of AI agents and language models. 
Its primary goal is to facilitate complex AI-based research tasks with ease and efficiency.

EDSL is developed by `Expected Parrot <https://www.expectedparrot.com>`_ and available under the MIT License.


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
EDSL supports various question types (free text, multiple choice, etc.) that can be grouped into a `Survey` that operates either in parallel or based on specific rules and conditional logic. 

A question can also be parameterized with a `Scenario` to provide contextual data or variations in the prompts that are presented to the language model(s), facilitating simultaneous administration of different versions of questions. 
This functionality can be particularly useful for data labeling tasks, where a question can be administered for each piece of data in a dataset at once to produce an annotated dataset. 

EDSL surveys can also be executed with multiple agents and models concurrently, offering diverse and rich response types, essential for robust data analysis and application.


Key components
--------------

The following concepts form the basic classes of the EDSL package, and are described in detail in the linked pages:

:ref:`questions`: A `Question` serves as the foundational element for research design in EDSL. 
It allows users to choose from various question types, such as free text or multiple choice, depending on the desired outcome for format of the responses.

:ref:`surveys`: A `Survey` aggregates multiple questions, which can be administered either asynchronously (by default) or according to predefined rules. 
Surveys are versatile, supporting different agents and models to yield varied responses. 
They can also incorporate diverse "scenarios" that supply context and data, enhancing the depth and relevance of the questions posed.

:ref:`agents`: An `Agent` represents an AI entity programmed to respond to the questions. 
Each agent can possess unique traits that influence their responses, including their background, expertise, or memory of previous interactions within the survey.

:ref:`language_models`: A `Model` refers to a large language model that generates answers to the questions. 
EDSL is designed to be model-agnostic, enabling the integration of multiple models to facilitate response comparison and selection.

:ref:`scenarios`: A `Scenario` provides specific context or data to a question at the time of its execution. 
This feature allows for dynamic parameterization of questions, enabling the same question to be adapted and asked across varied contexts efficiently.

:ref:`results`: A `Result` is the direct output obtained from executing a question. 
Results include information about the question, agent, model, and the generated response.
They can be analyzed, visualized, shared, and utilized to refine further inquiries or enhance the structure of subsequent surveys.


How it works
------------

EDSL operates by combining these key components to create and execute surveys, generating responses from AI agents using language models.

A quick example 
^^^^^^^^^^^^^^^

An EDSL survey can be as simple as a single question. 
We select a question type (e.g., multiple choice), construct a question and call the `run()` method to generate a response from the default language model (GPT-4):

.. code-block:: python

   from edsl import QuestionMultipleChoice

   q = QuestionMultipleChoice(
      question_name = "registered",
      question_text = "Are you currently registered to vote?",
      question_options = ["Yes", "No", "I don't know"]
   )

   results = q.run()


We can use built-in methods to inspect the response:

.. code-block:: python

   results.select("model", "registered").print(format="rich")


This will return:

.. code-block:: text

   ┏━━━━━━━━━━━━━┓
   ┃ answer      ┃
   ┃ .registered ┃
   ┡━━━━━━━━━━━━━┩
   │ Yes         │
   └─────────────┘


A more complex example
^^^^^^^^^^^^^^^^^^^^^^

We can administer multiple questions at once by passing them to a `Survey` object.
We can also add survey rules and agent memory of other questions to control the flow of questions and responses:

.. code-block:: python

   from edsl import QuestionMultipleChoice, QuestionYesNo, QuestionFreeText, QuestionCheckBox, Survey

   q1 = QuestionMultipleChoice(
      question_name = "registered",
      question_text = "Are you currently registered to vote?",
      question_options = ["Yes", "No", "I don't know"]
   )
   q2 = QuestionYesNo(
      question_name = "eligible",
      question_text = "Are you eligible to vote?"
   )
   q3 = QuestionFreeText(
      question_name = "factors",
      question_text = "What factors most influence your decision to vote in an election?"
   )
   q4 = QuestionCheckBox(
      question_name = "issues",
      question_text = "Which issues are most important to you?",
      question_options = ["Economy", "Healthcare", "Education", "Climate change", "National security", "Other"]
   )

   survey = (
      Survey([q1, q2, q3, q4])  # Add questions to the survey
      .add_skip_rule(q2, "registered == 'Yes'")  # Add conditional logic 
      .add_targeted_memory(q4, q3)  # Add agent memory
   )

   results = survey.run()

   results.select("registered", "eligible", "factors", "issues").print(format="rich")


Output:

.. code-block:: text

   ┏━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┓
   ┃ answer      ┃ answer    ┃ answer                                                           ┃ answer             ┃
   ┃ .registered ┃ .eligible ┃ .factors                                                         ┃ .issues            ┃
   ┡━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━┩
   │ Yes         │ None      │ The factors that most influence my decision to vote in an        │ ['Climate change'] │
   │             │           │ election include the candidates' policies and their alignment    │                    │
   │             │           │ with my personal values, the impact of the election on local and │                    │
   │             │           │ national issues, the integrity and track record of the           │                    │
   │             │           │ candidates, the importance of civic duty and the democratic      │                    │
   │             │           │ process, and the potential for meaningful change or the          │                    │
   │             │           │ preservation of stability within the community and the country.  │                    │
   └─────────────┴───────────┴──────────────────────────────────────────────────────────────────┴────────────────────┘


Agents & Models 
^^^^^^^^^^^^^^^

We can design personas for AI agents and select language models to generate responses:

.. code-block:: python

   from edsl import AgentList, Agent, ModelList, Model

   agents = AgentList(
      Agent(traits = {"party":p, "age":a}) 
      for p in ["Democrat", "Republican", "Independent"] for a in [25, 60]
   )

   models = ModelList(
      Model(m) for m in ["gpt-4", "claude-3-5-sonnet-20240620"]
   )

   results = survey.by(agents).by(models).run()


We can then filter, sort, and select specific results for analysis:

.. code-block:: python

   (results
   .filter("age == 60")
   .sort_by("model", "party")
   .select("model", "party", "age", "issues")
   .print(pretty_labels = {
      "model.model":"Model", 
      "agent.party":"Party", 
      "agent.age":"Age", 
      "answer.issues":q4.question_text + "\n" + ", ".join(q4.question_options)},
         format="rich")
   )


Output:

.. code-block:: text

   ┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
   ┃                            ┃             ┃     ┃ Which issues are most important to you?                        ┃
   ┃                            ┃             ┃     ┃ Economy, Healthcare, Education, Climate change, National       ┃
   ┃ Model                      ┃ Party       ┃ Age ┃ security, Other                                                ┃
   ┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
   │ claude-3-5-sonnet-20240620 │ Democrat    │ 60  │ ['Healthcare', 'Climate change']                               │
   ├────────────────────────────┼─────────────┼─────┼────────────────────────────────────────────────────────────────┤
   │ claude-3-5-sonnet-20240620 │ Independent │ 60  │ ['Economy', 'Healthcare', 'National security']                 │
   ├────────────────────────────┼─────────────┼─────┼────────────────────────────────────────────────────────────────┤
   │ claude-3-5-sonnet-20240620 │ Republican  │ 60  │ ['Economy', 'National security']                               │
   ├────────────────────────────┼─────────────┼─────┼────────────────────────────────────────────────────────────────┤
   │ gpt-4                      │ Democrat    │ 60  │ ['Healthcare', 'Education', 'Climate change']                  │
   ├────────────────────────────┼─────────────┼─────┼────────────────────────────────────────────────────────────────┤
   │ gpt-4                      │ Independent │ 60  │ ['Economy', 'Healthcare', 'Climate change', 'National          │
   │                            │             │     │ security']                                                     │
   ├────────────────────────────┼─────────────┼─────┼────────────────────────────────────────────────────────────────┤
   │ gpt-4                      │ Republican  │ 60  │ ['Economy', 'National security']                               │
   └────────────────────────────┴─────────────┴─────┴────────────────────────────────────────────────────────────────┘


Creating scenarios of questions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We can parameterize questions with context or data to administer multiple versions of questions at once.
This is done by creating `Scenario` objects that are added to a survey in the same way as agents and models.
Scenarios can be particularly useful for data labeling tasks or when conducting surveys across different contexts:

.. code-block:: python

   from edsl import QuestionLinearScale, ScenarioList, Scenario

   q6 = QuestionMultipleChoice(
      question_name = "primary_news_source",
      question_text = "What is your primary source of news about {{ topic }}?",
      question_options = [
         "Television",
         "Online news websites",
         "Social media",
         "Newspapers",
         "Radio",
         "Other"
      ]
   )
   q7 = QuestionLinearScale(
      question_name = "optimistic",
      question_text = "On a scale from 1 to 10, how optimistic do you feel about {{ topic }}?",
      question_options = [1,2,3,4,5,6,7,8,9,10],
      option_labels = {1:"Not at all optimistic", 10:"Very optimistic"}
   )

   survey = Survey([q6, q7])

   scenarios = ScenarioList(
      Scenario({"topic":t}) for t in ["Economy", "Healthcare", "Education", "Climate change", "National security"]
   )

   results = survey.by(scenarios).by(agents).run()

   (results
   .filter("optimistic > '7' and age == 25")
   .sort_by("optimistic", "party")
   .select("party", "age", "topic", "primary_news_source", "optimistic")
   .print(format="rich")
   )


Output:  

.. code-block:: text

   ┏━━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┓
   ┃ agent       ┃ agent ┃ scenario          ┃ answer               ┃ answer      ┃
   ┃ .party      ┃ .age  ┃ .topic            ┃ .primary_news_source ┃ .optimistic ┃
   ┡━━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━┩
   │ Democrat    │ 25    │ Education         │ Online news websites │ 8           │
   ├─────────────┼───────┼───────────────────┼──────────────────────┼─────────────┤
   │ Independent │ 25    │ Education         │ Online news websites │ 8           │
   ├─────────────┼───────┼───────────────────┼──────────────────────┼─────────────┤
   │ Republican  │ 25    │ National security │ Online news websites │ 8           │
   └─────────────┴───────┴───────────────────┴──────────────────────┴─────────────┘


EDSL comes with built-in methods for data analysis and visualization, making it easy to explore and interpret the results of your research.
Examples of these methods are provided in the :ref:`results` section.


Key features 
------------

EDSL offers a range of features that make it a powerful tool for conducting AI-powered research:

*Declarative Design*
EDSL's declarative design simplifies the creation and execution of complex research tasks, enabling users to achieve more with less code.

*Flexible Survey Construction*
Users can create surveys with multiple questions, rules, and conditional logic, and administer them to diverse agents and models simultaneously.

*Parameterized Questions*
Questions can be parameterized with scenarios to provide context or data, facilitating the administration of multiple versions of questions at once.

*Agent and Model Selection*
EDSL supports the design of AI agents with unique traits and the selection of language models to generate responses, enabling diverse and rich response types.

*Built-in Data Analysis*
EDSL provides built-in methods for analyzing and visualizing survey results, making it easy to explore and interpret research outcomes.

*Remote Caching and Inference*
EDSL offers remote caching and inference features to store and share survey results and offload processing tasks to the Expected Parrot server.

*Python Integration*
EDSL leverages Python's robust ecosystem, seamlessly integrating with existing Python tools. 
It is ideally used within a notebook environment, facilitating the execution and detailed analysis of research outcomes. 

*Model Agnosticism*
The framework's design allows for the application of diverse language models and agents to the same set of questions, enabling comparative analysis across different models.

*Open Source Flexibility*
EDSL is open-source under a permissive license, offering the freedom to use, modify, and extend it for personal or commercial projects.


Coop: Collaborative Research Platform
-------------------------------------

*Enhancing Research Collaboration*
EDSL promotes not only the creation of research but also the sharing of insights, code and results. 
:ref:`coop` is a new platform designed to enhance collaborative research efforts by providing a centralized location for storing and sharing EDSL content and AI research.
It provides a range of features, including:

*Automatic Caching and Versioning*
Automatically store survey results and API calls on the Expected Parrot server to ensure that all aspects of your research are tracked and retrievable.

*Remote Inference*
Run jobs on the Expected Parrot server to offload processing tasks, avoid the need to manage local resources and API keys, and speed up research execution. 

See the :ref:`coop` section for more information on how to use these features.


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

See our :ref:`starter_tutorial`, how-to guides and notebooks for examples as well.



Links
-----

- `Download the latest version of EDSL on **PyPI** <https://pypi.org/project/edsl>`_.

- `Get the latest EDSL updates on **GitHub** <https://github.com/expectedparrot/edsl>`_.

- `Create a **Coop** account <https://www.expectedparrot.com/login>`_.

- `Join our **Discord** channel <https://discord.com/invite/mxAYkjfy9m>`_ to connect with other users and ask questions.

- Follow us on social media:
  - `Twitter/X <https://twitter.com/expectedparrot>`_
  - `LinkedIn <https://www.linkedin.com/company/expectedparrot>`_
  - `Blog <https://blog.expectedparrot.com>`_


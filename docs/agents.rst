.. _agents:

Agents
======

`Agent` objects are used to simulate survey responses for target audiences. 
They can be created with specified traits, such as personas and relevant attributes for a survey, that are used together with language models to generate answers to questions. 

Agents can be created individually or as a list of agents, and can be updated after they are created.
They can be used with any question type, and can be used to generate responses for a single question or a survey of multiple questions.

Agent information is presented to a model in a system prompt; it is delivered together with a user prompt of information about a given question.
In the examples below we show how to access these prompts to inspect them before running a survey and in the results that are generated for a survey.
Note, however, that certain models do not take system prompts (e.g., OpenAI's o1). 
When using a model that does not take a system prompt, agent information should be included in the user prompt.


Constructing an Agent
---------------------

An `Agent` is created by passing a dictionary of `traits` for a model to reference in answering questions. 
Traits can be anything that might be relevant to the questions the agent will be asked, and constructed with single values or textual narratives.

For example:

.. code-block:: python

    from edsl import Agent

    agent = Agent(
        traits = {
            "persona": "You are an expert in machine learning.",
            "age": 45,
            "home_state": "Massachusetts"
        })


Note that `traits=` must be named explicitly in the construction, and the traits must use Python identifiers as keys (e.g., `home_state` but not `home state` or `home-state`).
    

Agent names 
-----------

We can optionally give an agent a name when it is constructed:

.. code-block:: python

    agent = Agent(
        name = "Ada", 
        traits = {
            "persona": "You are an expert in machine learning.",
            "age": 45,
            "home_state": "Massachusetts"
        })


If a name is not passed when the agent is created, an `agent_name` field is automatically added to the `Results` that are generated when a survey is run with the agent.
This field is a unique identifier for the agent and can be used to filter or group results by agent.
It is *not* used in the prompts for generating responses.
If you want to use a name in the prompts for generating responses, you can pass it as a trait:

.. code-block:: python

    agent = Agent(
        traits = {
            "first_name": "Ada",
            "persona": "You are an expert in machine learning.",
            "age": 45,
            "home_state": "Massachusetts"
        })


We can see how the agent information is presented to a model by inspecting the system prompt that is generated when we use an agent with a question:

.. code-block:: python

    from edsl import QuestionFreeText

    q = QuestionFreeText(
        question_name = "favorite_food",
        question_text = "What is your favorite food?"
    )

    job = q.by(agent) # using the agent created above
    job.prompts().select("user_prompt", "system_prompt")


Output:

.. list-table::
   :header-rows: 1

   * - user_prompt
     - system_prompt
   * - What is your favorite food?
     - ou are answering questions as if you were a human. Do not break character. Your traits: {'first_name': 'Ada', 'persona': 'You are an expert in machine learning.', 'age': 45, 'home_state': 'Massachusetts'}


Note that trying to create two agents with the same name or trying to use a key "name" in the `traits` will raise an error.


Agent lists
-----------

Agents can be created collectively and administered a survey together. 
This is useful for comparing responses for multiple agents.

For example, here we create an a list of agents as an `AgentList` with different combinations of traits: 

.. code-block:: python

    from edsl import AgentList, Agent

    ages = [10, 20, 30, 40, 50]
    locations = ["New York", "California", "Texas", "Florida", "Washington"]

    agents = AgentList(
        Agent(traits = {"age": age, "location": location}) for age, location in zip(ages, locations)
    ) 


This code will create a list of agents that can then be used in a survey.

Example code for running a survey with the agents:

.. code-block:: python

    from edsl import QuestionFreeText, Survey

    q = QuestionFreeText(
        question_name = "favorite_food",
        question_text = "What is your favorite food?"
    )

    survey = Survey(questions = [q])

    results = survey.by(agents).run()


This will generate a `Results` object that contains a `Result` for each agent's responses to the survey question.
Learn more about working with results in the :ref:`results` section.


Generating agents from data 
---------------------------

An `AgentList` can be automatically generated from data stored in a list, a dictionary or a CSV file.


From a list
^^^^^^^^^^^

We can create a simple `AgentList` from a list using the `from_list()` method, which takes a single `trait_name` and a list of `values` for it and returns an agent for each value (each agent has a single trait):

.. code-block:: python

    from edsl import AgentList

    agents = AgentList.from_list(trait_name="age", values=[10, 20, 30, 40])
    agents


Output:

.. list-table::
   :header-rows: 1

   * - age
   * - 10
   * - 20
   * - 30
   * - 40


From a dictionary
^^^^^^^^^^^^^^^^^

We can create a more complex `AgentList` from a dictionary using the `from_dict()` method.
It takes a dictionary with a key `agent_list` and a list of dictionaries, each of which must have a `traits` key with a dictionary of traits and an optional `name` key for the agent's name:

.. code-block:: python

    from edsl import AgentList

    data = {
        "agent_list": [
            {"name":"agent1", "traits":{"age": 10, "location": "New York"}},
            {"name":"agent2", "traits":{"age": 20, "location": "California"}},
            {"name":"agent3", "traits":{"age": 30, "location": "Texas"}},
            {"name":"agent4", "traits":{"age": 40, "location": "Florida"}},
            {"name":"agent5", "traits":{"age": 50, "location": "Washington"}}
        ]
    }

    agents = AgentList.from_dict(data)
    agents


Output:

.. list-table::
   :header-rows: 1

   * - location
     - age
   * - New York
     - 10
   * - California
     - 20
   * - Texas
     - 30
   * - Florida
     - 40
   * - Washington
     - 50


From a CSV file
^^^^^^^^^^^^^^^

We can also create an `AgentList` from a CSV file using the `from_csv()` method.
The CSV file must have a header row of Pythonic keys for the `traits`, and can optionally have a column "name" for the agent names:

.. code-block:: python

    from edsl import AgentList

    # Creating a CSV file with agent data to use as an example
    import pandas as pd

    data = [
        {"name": "Alice", "age": 25, "city": "New York"},
        {"name": "Bob", "age": 30, "city": "San Francisco"},
        {"name": "Charlie", "age": 35, "city": "Chicago"}
    ]

    df = pd.DataFrame(data)

    df.to_csv("agent_data.csv", index=False)

    # Creating an AgentList from the CSV file
    agents = AgentList.from_csv("agent_data.csv")
    agents


Output:

.. list-table::
   :header-rows: 1

   * - city
     - age
   * - New York
     - 25
   * - San Francisco
     - 30
   * - Chicago
     - 35


Dynamic traits function
-----------------------

Agents can also be created with a `dynamic_traits_function` parameter. 
This function can be used to generate traits dynamically based on the question being asked or the scenario in which the question is asked.

*Note:* This method is only available with local inference. It does not work with remote inference.

Example:

.. code-block:: python

    def dynamic_traits_function(question):
        if question.question_name == "age":
            return {"age": 10}
        elif question.question_name == "hair":
            return {"hair": "brown"}

    a = Agent(dynamic_traits_function = dynamic_traits_function)


When the agent is asked a question about age, the agent will return an age of 10. 
When asked about hair, the agent will return "brown".
This can be useful for creating agents that can answer questions about different topics without including potentially irrelevant traits in the agent's traits dictionary.

Note that the traits returned by the function are *not* added to the agent's traits dictionary.


Agent direct-answering methods
------------------------------

Agents can also be created with a method that can answer a particular question type directly:

.. code-block:: python

    from edsl import Agent 

    a = Agent()

    def f(self, question, scenario): return "I am a direct answer."

    a.add_direct_question_answering_method(f)
    a.answer_question_directly(question = None, scenario = None)


Output:

.. code-block:: text

    I am a direct answer.


This can be useful for creating agents that can answer questions directly without needing to use a language model.


Giving an agent instructions
----------------------------

In addition to traits, agents can be given detailed instructions on how to answer questions.

For example:

.. code-block:: python

    from edsl import Agent

    a = Agent(traits = {"age": 10}, instruction = "Answer in German.")
    a.instruction


Output:

.. code-block:: text

    Answer in German.


When the agent is assigned to a survey, the special instruction will be added to the prompts for generating responses.
The instructions are stored in the `instruction` field of the agent and can be accessed directly in results.

Learn more about how to use instructions in the :ref:`prompts` section.


Controlling the presentation of the persona
-------------------------------------------

The `traits_presentation_template` parameter can be used to create a narrative persona for an agent.
This is a template string that can be rendered with the agent's traits as variables.

For example:

.. code-block:: python

    a = Agent(
        traits = {'age': 22, 'hair': 'brown', 'gender': 'female'}, 
        traits_presentation_template = "I am a {{ age }} year-old {{ gender }} with {{ hair }} hair."
        )

    a.agent_persona.render(primary_replacement = a.traits)


Output:

.. code-block:: text

    I am a 22 year-old female with brown hair.


Note that the trait keys must be valid Python identifiers (e.g., `home_state` but not `home state` or `home-state`).
This can be handled by using a dictionary with string keys and values, for example:

.. code-block:: python

    from edsl import Agent

    codebook = {'age': 'The age of the agent'}

    a = Agent(
        traits = {'age': 22}, 
        codebook = codebook, 
        traits_presentation_template = "{{ codebook['age'] }} is {{ age }}."
        )

    a.agent_persona.render(primary_replacement = a.traits)


Output:

.. code-block:: text

    The age of the agent is 22.


Note that it can be helpful to include traits mentioned in the persona as independent keys and values in order to analyze survey results by those dimensions individually.
For example, we may want the narrative to include a sentence about the agent's age, but also be able to readily analyze or filter results by age.

The following code will include the agent's age as a column of a table with any other selected components (e.g., agent name and all the answers):

.. code-block:: python

    results.select("agent.age", "agent.agent_name", "answer.*")


Note that the prefix "agent" can also be dropped. The following code is equivalent:

.. code-block:: python

    results.select("age", "agent_name", "answer.*")


We can filter the results by an agent's traits:

.. code-block:: python

    results.filter("age == 22")


We can also call the `filter()` method on an agent list to filter agents by their traits:

.. code-block:: python

    middle_aged_agents = agents.filter("40 <= age <= 60")



Using agent traits in prompts 
-----------------------------

The `traits` of an agent can be used in the prompts of questions. 

For example:

.. code-block:: python

    from edsl import Agent, QuestionFreeText 

    a = Agent(traits = {'first_name': 'John'})

    q = QuestionFreeText(
        question_text = 'What is your last name, {{ agent.first_name }}?', 
        question_name = "exmaple"
    )

    job = q.by(a)
    job.prompts().select("user_prompt")


Output:

.. list-table::
   :header-rows: 1

   * - user_prompt
   * - What is your last name, John?


Learn more about user and system prompts in the :ref:`prompts` section.


Accessing agent traits 
----------------------

The `traits` of an agent can be accessed directly:

.. code-block:: python

    from edsl import Agent 

    a = Agent(traits = {'age': 22})
    a.traits


Output:

.. code-block:: text

    {'age': 22}


The `traits` of an agent can also be accessed as attributes of the agent:

.. code-block:: python

    from edsl import Agent

    a = Agent(traits = {'age': 22})
    a.age


Output:

.. code-block:: text

    22
    

Simulating agent responses 
--------------------------
    
When a survey is run, agents can be assigned to it using the `by` method, which can be chained with other components like scenarios and models:

.. code-block:: python 

    from edsl import Agent, QuestionList, QuestionMultipleChoice, Survey

    agent = Agent(
        name = "college student",
        traits = {
            "persona": "You are a sophomore at a community college in upstate New York.",
            "year": "sophomore",
            "school": "community college",
            "major": "biology",
            "state": "New York"
        }
    )

    q1 = QuestionList(
        question_name = "favorite_courses",
        question_text = "What are the names of your 3 favorite courses?",
        max_list_items = 3
    )

    q2 = QuestionMultipleChoice(
        question_name = "attend_grad_school",
        question_text = "Do you plan to attend grad school?",
        question_options = ["Yes", "No", "Undecided"]
    )

    survey = Survey([q1, q2])

    results = survey.by(agent).run()


This will generate a `Results` object that contains a `Result` for each agent's responses to the survey questions.
We can select and inspect components of the results, such as the agent's traits and their answers:

.. code-block:: python

    results.select("persona", "year", "school", "major", "state", "answer.*")


Output:

.. list-table::
   :header-rows: 1

   * - agent.persona
     - agent.year
     - agent.school
     - agent.major
     - agent.state
     - answer.favorite_courses
     - answer.attend_grad_school
   * - You are a sophomore at a community college in upstate New York.
     - sophomore
     - community college
     - biology
     - New York
     - ['General Biology I', 'Organic Chemistry', 'Environmental Science']
     - Undecided


If multiple agents will be used with a survey, they are passed as a list in the same `by` call:

.. code-block:: python 

    from edsl import Agent, AgentList

    agents = AgentList([
        Agent(traits = {"major": "biology", "year": "sophomore"}),
        Agent(traits = {"major": "history", "year": "junior"}),
        Agent(traits = {"major": "mathematics", "year": "senior"}),
    ])

    results = survey.by(agents).run() # using the same survey as above

    results.select("major", "year", "answer.*")


Output:

.. list-table::
   :header-rows: 1

   * - agent.major
     - agent.year
     - answer.favorite_courses
     - answer.attend_grad_school
   * - biology
     - sophomore
     - ['Genetics', 'Ecology', 'Cell Biology']
     - Undecided
   * - history
     - junior
     - ['Medieval Europe', 'The American Civil War', 'Ancient Civilizations']
     - Undecided
   * - mathematics
     - senior
     - ['Abstract Algebra', 'Real Analysis', 'Topology']
     - Undecided


If scenarios and/or models are also specified for a survey, each component type is added in a separate `by` call that can be chained in any order with the `run` method appended last:

.. code-block:: python 

    results = survey.by(scenarios).by(agents).by(models).run() # example code - scenarios and models not defined here


Learn more about :ref:`scenarios`, :ref:`language_models` and :ref:`results`.


Updating agents 
---------------

Agents can be updated after they are created.


Changing a trait
^^^^^^^^^^^^^^^^

Here we create an agent and then change one of its traits:

.. code-block:: python

    from edsl import Agent

    a = Agent(traits = {"age": 22})
    a.age = 23
    a.age


Output:

.. code-block:: text

    23


Adding a trait
^^^^^^^^^^^^^^

We can also add a new trait to an agent:

.. code-block:: python

    from edsl import Agent

    a = Agent(traits = {"age": 22})

    a.add_trait({"location": "California"})
    a


Output:

.. list-table::
    :header-rows: 1

    * - key
      - value
    * - traits:age
      - 22
    * - traits:location
      - California


Removing a trait
^^^^^^^^^^^^^^^^

We can remove a trait from an agent:

.. code-block:: python

    from edsl import Agent

    a = Agent(traits = {"age": 22, "location": "California"})

    a.remove_trait("age")
    a


Output:

.. list-table::
    :header-rows: 1

    * - key
      - value
    * - traits:location
      - California


Using survey responses as new agent traits
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

After running a survey, we can use the responses to create new traits for an agent:

.. code-block:: python

    from edsl import Agent, QuestionMultipleChoice, Survey

    a = Agent(traits = {"age": 22, "location": "California"})

    q = QuestionMultipleChoice(
        question_name = "surfing",
        question_text = "How often do you go surfing?",
        question_options = ["Never", "Sometimes", "Often"]
    )

    survey = Survey([q])
    results = survey.by(a).run()

    a = results.select("age", "location", "surfing").to_agent_list() # create new agent with traits from results
    a


Output: 

.. list-table::
  :header-rows: 1

  * - location
    - surfing
    - age
  * - California
    - Sometimes
    - 22


Note that in the example above we simply replaced the original agent by selecting the first agent from the agent list that we created.
This can be useful for creating agents that evolve over time based on their experiences or responses to surveys.

Here we use the same method to update multiple agents at once:

.. code-block:: python

    from edsl import Agent, QuestionMultipleChoice, Survey, AgentList

    agents = AgentList([
        Agent(traits = {"age": 22, "location": "California"}),
        Agent(traits = {"age": 30, "location": "New York"}),
        Agent(traits = {"age": 40, "location": "Texas"}),
    ])

    q = QuestionMultipleChoice(
        question_name = "surfing",
        question_text = "How often do you go surfing?",
        question_options = ["Never", "Sometimes", "Often"]
    )

    survey = Survey([q])
    results = survey.by(agents).run()

    agents = results.select("age", "location", "surfing").to_agent_list() 
    agents


Output:

.. list-table::
  :header-rows: 1

  * - location
    - surfing
    - age
  * - California
    - Sometimes
    - 22
  * - New York
    - Never
    - 30
  * - Texas
    - Never
    - 40


Agent class
-----------
.. automodule:: edsl.agents.Agent
   :members:
   :undoc-members:
   :show-inheritance:
   :special-members: __init__
   :exclude-members: codebook, data, main
   
   
AgentList class
---------------
.. automodule:: edsl.agents.AgentList
   :noindex:

.. automethod:: AgentList.__init__
   :noindex:
   
.. automethod:: AgentList.example
   :noindex:
   
.. automethod:: AgentList.from_dict
   :noindex:

.. automethod:: AgentList.from_csv
   :noindex:

.. automethod:: AgentList.from_list
   :noindex:
   
.. automethod:: AgentList.to_dict
   :noindex:

.. automethod:: AgentList.to_csv
   :noindex:

.. automethod:: AgentList.rich_print
   :noindex:


.. Invigilator class
.. -----------------
.. The administration of Questions is managed by an `Invigilator`.

.. .. automodule:: edsl.agents.Invigilator
..    :members:
..    :undoc-members:
..    :show-inheritance:

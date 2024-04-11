.. _agents:

Agents
======
An `Agent` can reference a set of traits in answering questions.
Agent characteristics and capabilties are used together with language models to influence how a question is answered. 

Constructing an Agent
---------------------
An `Agent` is created by passing a dictionary of `traits` for the agent to reference in answering questions. 
Traits can be anything that might be relevant to the questions the agent will be asked, and constructed with single values or textual narratives:

.. code-block:: python

    traits_dict = {
        "persona": "You are a 45-old-woman living in Massachusetts...",
        "age": 45,
        "location": "Massachusetts"
    }
    a = Agent(traits = traits_dict)

Note that `traits=` must be named explicitly in the construction, and the traits must use Python identifiers as keys (e.g., `home_state` but not `home state` or `home-state`).
    
Agent names 
-----------
We can optionally give an agent a name when it is constructed:

.. code-block:: python

    agent = Agent(name = "Robin", traits = traits_dict)

If a name is not passed when the agent is created, an `agent_name` field is automatically added to results when a survey is administered to the agent.
This field is a unique identifier for the agent and can be used to filter or group results by agent.

Note that trying to create two agents with the same name or trying to include the name in the traits will raise an error.

Agent lists
-----------
Agents can be created collectively and administered a survey together. 
This is useful for comparing responses across agents.
The following example creates a list of agents with each combination of listed trait dimensions: 

.. code-block:: python

    ages = [10, 20, 30, 40, 50]
    locations = ["New York", "California", "Texas", "Florida", "Washington"]
    agents = [Agent(traits = {"age": age, "location": location}) 
        for age, location in zip(ages, locations)]

Dynamic traits function
-----------------------
Agents can also be created with a `dynamic_traits_function` parameter. 
This function can be used to generate traits dynamically based on the question being asked or the scenario in which the question is asked.
For example:

.. code-block:: python

    def dynamic_traits_function(self, question):
        if question.question_name == "age":
            return {"age": 10}
        elif question.question_name == "hair":
            return {"hair": "brown"}

    a = Agent(dynamic_traits_function = dynamic_traits_function)

When the agent is asked a question about age, the agent will return an age of 10. 
When asked about hair, the agent will return "brown".
This can be useful for creating agents that can answer questions about different topics without 
including potentially irrelevant traits in the agent's traits dictionary.

Agent direct-answering methods
------------------------------
Agents can also be created with a method that can answer a particular question type directly:

.. code-block:: python

    a = Agent()
    def f(self, question, scenario): return "I am a direct answer."
    a.add_direct_question_answering_method(f)
    a.answer_question_directly(question = None, scenario = None)

This code will return:

.. code-block:: text

    I am a direct answer.

This can be useful for creating agents that can answer questions directly without needing to use a language model.

Giving an agent instructions
----------------------------
In addition to traits, agents can be given detailed instructions on how to answer questions.
For example:

.. code-block:: python

    a = Agent(traits = {"age": 10}, instruction = "Answer in German.")
    a.instruction


Controlling the presentation of the persona
-------------------------------------------
The `traits_presentation_template` parameter can be used to create a narrative persona for an agent.
This is a template string that can be rendered with the agent's traits as variables.
For example:

.. code-block:: python

    a = Agent(traits = {'age': 22, 'hair': 'brown', 'gender': 'female'}, 
        traits_presentation_template = \"\"\"
            I am a {{ age }} year-old {{ gender }} with {{ hair }} hair.\"\"\")
    a.agent_persona.render(primary_replacement = a.traits)

This code will return:

.. code-block:: text

    I am a 22 year-old female with brown hair.

Note that the trait keys must be valid Python identifiers (e.g., `home_state` but not `home state` or `home-state`).
This can be handled by using a dictionary with string keys and values, for example:

.. code-block:: python

    codebook = {'age': 'The age of the agent'}
    a = Agent(traits = {'age': 22}, 
        codebook = codebook, 
        traits_presentation_template = "{{ codebook['age'] }} is {{ age }}.")
    a.agent_persona.render(primary_replacement = a.traits)

This code will return:

.. code-block:: text

    The age of the agent is 22.

Note that it can be helpful to include traits mentioned in the persona as independent keys and values in order to analyze survey results by those dimensions individually.
For example, we may want the narrative to include a sentence about the agent's age, but also be able to readily analyze or filter results by age.

The following code will include the agent's age as a column of a table with any other selected components:

.. code-block:: python

    results.select("agent.age", ...).print()

And this code will let us filter the results by the agent's age:

.. code-block:: python

    results.filter("agent.age == 22").print()


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
   
.. automethod:: AgentList.rich_print
   :noindex:
   
.. automethod:: AgentList.to_dict
   :noindex:
   
.. Invigilator class
.. -----------------
.. The administration of Questions is managed by an `Invigilator`.

.. .. automodule:: edsl.agents.Invigilator
..    :members:
..    :undoc-members:
..    :show-inheritance:

.. _agents:

Agents
======

.. An Agent is an AI agent that can reference a set of traits in answering questions.

Constructing an Agent
---------------------
Key steps:

* Create a dictionary of `traits` for an agent to reference in answering questions: 

.. code-block:: python

    traits_dict = {
        "persona": "You are a 45-old-woman living in Massachusetts...",
        "age": 45,
        "location": "Massachusetts"
    }
    a = Agent(traits = traits_dict)

    
Rendering traits as a narrative persona
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
The `traits_presentation_template` parameter can be used to create a narrative persona for an agent.

.. code-block:: python

    a = Agent(traits = {'age': 22, 'hair': 'brown', 'gender': 'female'}, 
        traits_presentation_template = \"\"\"
            I am a {{ age }} year-old {{ gender }} with {{ hair }} hair.\"\"\")
    a.agent_persona.render(primary_replacement = a.traits)

will return:

.. code-block:: text

    I am a 22 year-old female with brown hair.

The trait keys themselves must be valid Python identifiers.
This can create an issues, but it can be circumvented by using a dictionary with string keys and values. 

.. code-block:: python

    codebook = {'age': 'The age of the agent'}
    a = Agent(traits = {'age': 22}, 
        codebook = codebook, 
        traits_presentation_template = "{{ codebook['age'] }} is {{ age }}.")
    a.agent_persona.render(primary_replacement = a.traits)

will return:

.. code-block:: text

    The age of the agent is 22.

Note that it can be helpful to include traits mentioned in the persona as independent keys and values in order to analyze survey results by those dimensions individually.

* Create an Agent object with traits. Note that `traits=` must be named explicitly: 

.. code-block:: python

    agent = Agent(traits = traits_dict)

* Optionally give the agent a name: 

.. code-block:: python

    agent = Agent(name = "Robin", traits = traits_dict)

If a name is not assigned when the Agent is created, an `agent_name` field is added to results when a survey is administered to the agent.

Agents can also be created collectively and administered a survey together. This is useful for comparing responses across agents.
The following example creates a list of agents with each combination of listed trait dimensions: 

.. code-block:: python

    ages = [10, 20, 30, 40, 50]
    locations = ["New York", "California", 
        "Texas", "Florida", "Washington"]
    agents = [Agent(traits = {"age": age, "location": location}) 
        for age, location in zip(ages, locations)]

A survey is administered to all agents in the list together: 

.. code-block:: python

    results = survey.by(agents).run()

See more details about surveys in the :ref:`surveys` module.


Dynamic traits function
^^^^^^^^^^^^^^^^^^^^^^^

Agents can also be created with a `dynamic_traits_function` parameter. 
This function can be used to generate traits dynamically based on the question being asked or the scenario in which the question is asked.
Consider this example:

.. code-block:: python

    def dynamic_traits_function(self, question):
        if question.question_name == "age":
            return {"age": 10}
        elif question.question_name == "hair":
            return {"hair": "brown"}

    a = Agent(dynamic_traits_function = dynamic_traits_function)

when the agent is asked a question about age, the agent will return an age of 10. 
When asked about hair, the agent will return "brown".
This can be useful for creating agents that can answer questions about different topics without 
including potentially irrelevant traits in the agent's traits dictionary.

Agent direct-answering methods
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Agents can also be created with a method that can answer a particular question type directly.

.. code-block:: python

    a = Agent()
    def f(self, question, scenario): return "I am a direct answer."
    a.add_direct_question_answering_method(f)
    a.answer_question_directly(question = None, scenario = None)

will return:

.. code-block:: text

    I am a direct answer.

This can be useful for creating agents that can answer questions directly without needing to use a language model.

Giving the agent instructions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Agents can also be given instructions on how to answer questions.

.. code-block:: python

    a = Agent(traits = {"age": 10}, instruction = "Answer as if you were a 10-year-old.")
    a.instruction


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

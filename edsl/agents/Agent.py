"""An Agent is an AI agent that can reference a set of traits in answering questions.


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


Agent class methods
-------------------
"""
from __future__ import annotations
import copy
import inspect
import types
from typing import Any, Callable, Optional, Union, Dict

from jinja2 import Template
from rich.console import Console
from rich.table import Table

from edsl.Base import Base

from edsl.exceptions.agents import (
    AgentCombinationError,
    AgentDirectAnswerFunctionError,
    AgentDynamicTraitsFunctionError,
)

from edsl.agents.Invigilator import (
    InvigilatorDebug,
    InvigilatorHuman,
    InvigilatorFunctional,
    InvigilatorAI,
    InvigilatorBase,
)

from edsl.language_models.registry import Model
from edsl.scenarios import Scenario
from edsl.enums import LanguageModelType

from edsl.agents.descriptors import (
    TraitsDescriptor,
    CodebookDescriptor,
    InstructionDescriptor,
    NameDescriptor,
)

from edsl.utilities.decorators import sync_wrapper
from edsl.data_transfer_models import AgentResponseDict
from edsl.prompts.library.agent_persona import AgentPersona


class Agent(Base):
    """An Agent that can answer questions."""

    default_instruction = """You are answering questions as if you were a human. Do not break character."""

    _traits = TraitsDescriptor()
    codebook = CodebookDescriptor()
    instruction = InstructionDescriptor()
    name = NameDescriptor()

    def __init__(
        self,
        *,
        traits: dict = None,
        name: str = None,
        codebook: dict = None,
        instruction: Optional[str] = None,
        traits_presentation_template: Optional[str] = None,
        dynamic_traits_function: Callable = None,
    ):
        """Initialize a new instance of Agent.

        :param traits: A dictionary of traits that the agent has. The keys need to be
        :param name: A name for the agent
        :param codebook: A codebook mapping trait keys to trait descriptions.
        :param instruction: Instructions for the agent in how to answer questions.
        :param trait_presentation_template: A template for how to present the agent's traits.
        :param dynamic_traits_function: A function that returns a dictionary of traits.

        Example usage:

        >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5})
        >>> a.traits
        {'age': 10, 'hair': 'brown', 'height': 5.5}

        >>> a = Agent(traits = {"age": 10}, traits_presentation_template = "I am a {{age}} year old.")
        >>> repr(a.agent_persona)
        Prompt(text='I am a 10 year old.') 
        """
        self.name = name
        self._traits = traits or dict()
        self.codebook = codebook or dict()
        self.instruction = instruction or self.default_instruction
        self.dynamic_traits_function = dynamic_traits_function
        self._check_dynamic_traits_function()
        self.current_question = None

        if traits_presentation_template is not None:
            self.traits_presentation_template = traits_presentation_template
            self.agent_persona = AgentPersona(text=self.traits_presentation_template)

    def _check_dynamic_traits_function(self) -> None:
        """Check whether dynamic trait function is valid.

        This checks whether the dynamic traits function is valid.
        """
        if self.dynamic_traits_function:
            sig = inspect.signature(self.dynamic_traits_function)
            if "question" in sig.parameters:
                if len(sig.parameters) > 1:
                    raise AgentDynamicTraitsFunctionError(
                        f"The dynamic traits function {self.dynamic_traits_function} has too many parameters. It should only have one parameter: 'question'."
                    )
            else:
                if len(sig.parameters) > 0:
                    raise AgentDynamicTraitsFunctionError(
                        f"""The dynamic traits function {self.dynamic_traits_function} has too many parameters. It should have no parameters or 
                        just a single parameter: 'question'."""
                    )

    @property
    def traits(self) -> dict[str, str]:
        """An agent's traits, which is a dictionary.

        The agent could have a a dynamic traits function (`dynamic_traits_function`) that returns a dictionary of traits
        when called. This function can also take a `question` as an argument.
        If so, the dynamic traits function is called and the result is returned.
        Otherwise, the traits are returned.

        Example:

        >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5})
        >>> a.traits
        {'age': 10, 'hair': 'brown', 'height': 5.5}

        """
        if self.dynamic_traits_function:
            sig = inspect.signature(self.dynamic_traits_function)
            if "question" in sig.parameters:
                return self.dynamic_traits_function(question=self.current_question)
            else:
                return self.dynamic_traits_function()
        else:
            return self._traits

    def add_direct_question_answering_method(self, method: Callable) -> None:
        """Add a method to the agent that can answer a particular question type.

        :param method: A method that can answer a question directly.

        Example usage:

        >>> a = Agent()
        >>> def f(self, question, scenario): return "I am a direct answer."
        >>> a.add_direct_question_answering_method(f)
        >>> a.answer_question_directly(question = None, scenario = None)
        'I am a direct answer.'
        """
        if hasattr(self, "answer_question_directly"):
            print("Warning: overwriting existing answer_question_directly method")

        signature = inspect.signature(method)
        for argument in ["question", "scenario", "self"]:
            if argument not in signature.parameters:
                raise AgentDirectAnswerFunctionError(
                    f"The method {method} does not have a '{argument}' parameter."
                )
        bound_method = types.MethodType(method, self)
        setattr(self, "answer_question_directly", bound_method)

    def create_invigilator(
        self,
        question: Question,
        scenario: Optional[Scenario] = None,
        model: Optional[LanguageModel] = None,
        debug: bool = False,
        memory_plan: Optional[MemoryPlan] = None,
        current_answers: Optional[dict] = None,
        iteration: int = 1,
    ) -> InvigilatorBase:
        """Create an Invigilator.

        An invigator is an object that is responsible administering a question to an agent and
        recording the responses.
        """
        self.current_question = question
        model = model or Model(LanguageModelType.GPT_4.value, use_cache=True)
        scenario = scenario or Scenario()
        invigilator = self._create_invigilator(
            question=question,
            scenario=scenario,
            model=model,
            debug=debug,
            memory_plan=memory_plan,
            current_answers=current_answers,
            iteration=iteration,
        )
        return invigilator

    async def async_answer_question(
        self,
        question: Question,
        scenario: Optional[Scenario] = None,
        model: Optional[LanguageModel] = None,
        debug: bool = False,
        memory_plan: Optional[MemoryPlan] = None,
        current_answers: Optional[dict] = None,
        iteration: int = 0,
    ) -> AgentResponseDict:
        """
        Answer a posed question.

        :param question: The question to answer.
        :param scenario: The scenario in which the question is asked.
        :param model: The language model to use.
        :param debug: Whether to run in debug mode.
        :param memory_plan: The memory plan to use.
        :param current_answers: The current answers.
        :param iteration: The iteration number.

        This is a function where an agent returns an answer to a particular question.
        However, there are several different ways an agent can answer a question, so the
        actual functionality is delegated to an Invigilator object.
        """
        invigilator = self.create_invigilator(
            question=question,
            scenario=scenario,
            model=model,
            debug=debug,
            memory_plan=memory_plan,
            current_answers=current_answers,
            iteration=iteration,
        )
        response: AgentResponseDict = await invigilator.async_answer_question()
        return response

    answer_question = sync_wrapper(async_answer_question)

    def _create_invigilator(
        self,
        question: Question,
        scenario: Optional[Scenario] = None,
        model: Optional[LanguageModel] = None,
        debug: bool = False,
        memory_plan: Optional[MemoryPlan] = None,
        current_answers: Optional[dict] = None,
        iteration: int = 0,
    ) -> InvigilatorBase:
        """Create an Invigilator."""
        model = model or Model(LanguageModelType.GPT_4.value, use_cache=True)
        scenario = scenario or Scenario()

        if debug:
            # use the question's _simulate_answer method
            # breakpoint()
            invigilator_class = InvigilatorDebug
        elif hasattr(question, "answer_question_directly"):
            # it is a functional question and the answer only depends on the agent's traits & the scenario
            invigilator_class = InvigilatorFunctional
        elif hasattr(self, "answer_question_directly"):
            # this of the case where the agent has a method that can answer the question directly
            # this occurrs when 'answer_question_directly' has been monkey-patched onto the agent
            # which happens when the agent is created from an existing survey
            invigilator_class = InvigilatorHuman
        else:
            # this means an LLM agent will be used. This is the standard case.
            invigilator_class = InvigilatorAI

        invigilator = invigilator_class(
            self,
            question=question,
            scenario=scenario,
            model=model,
            memory_plan=memory_plan,
            current_answers=current_answers,
            iteration=iteration,
        )
        return invigilator

    ################
    # Dunder Methods
    ################
    def __add__(self, other_agent: Agent = None) -> Agent:
        """
        Combine two agents by joining their traits.

        The agents must not have overlapping traits.

        Example usage:
        
        >>> a1 = Agent(traits = {"age": 10})
        >>> a2 = Agent(traits = {"height": 5.5})
        >>> a1 + a2
        Agent(traits = {'age': 10, 'height': 5.5})
        >>> a1 + a1
        Traceback (most recent call last):
        ...
        edsl.exceptions.agents.AgentCombinationError: The agents have overlapping traits: {'age'}.
        """
        if other_agent is None:
            return self
        elif common_traits := set(self.traits.keys()) & set(other_agent.traits.keys()):
            raise AgentCombinationError(
                f"The agents have overlapping traits: {common_traits}."
            )
        else:
            new_agent = Agent(traits=copy.deepcopy(self.traits))
            new_agent.traits.update(other_agent.traits)
            return new_agent

    def __eq__(self, other: Agent) -> bool:
        """Check if two agents are equal.

        This only checks the traits.
        >>> a1 = Agent(traits = {"age": 10})
        >>> a2 = Agent(traits = {"age": 10})
        >>> a1 == a2
        True
        >>> a3 = Agent(traits = {"age": 11})
        >>> a1 == a3
        False
        """
        return self.data == other.data

    def __repr__(self):
        """Return representation of Agent."""
        class_name = self.__class__.__name__
        items = [
            f"{k} = '{v}'" if isinstance(v, str) else f"{k} = {v}"
            for k, v in self.data.items()
            if k != "question_type"
        ]
        return f"{class_name}({', '.join(items)})"

    ################
    # SERIALIZATION METHODS
    ################
    @property
    def data(self):
        """Format the data for serialization.
        
        TODO: Warn if has dynamic traits function or direct answer function that cannot be serialized.
        TODO: Add ability to have coop-hosted functions that are serializable.
        """
        raw_data = {
            k.replace("_", "", 1): v
            for k, v in self.__dict__.items()
            if k.startswith("_")
        }
        if hasattr(self, "set_instructions"):
            if not self.set_instructions:
                raw_data.pop("instruction")
        if self.codebook == {}:
            raw_data.pop("codebook")
        if self.name == None:
            raw_data.pop("name")
        return raw_data

    def to_dict(self) -> dict[str, Union[dict, bool]]:
        """Serialize to a dictionary."""
        return self.data

    @classmethod
    def from_dict(cls, agent_dict: dict[str, Union[dict, bool]]) -> Agent:
        """Deserialize from a dictionary."""
        return cls(**agent_dict)

    ################
    # DISPLAY Methods
    ################

    def _table(self) -> tuple[dict, list]:
        """Prepare generic table data."""
        table_data = []
        for attr_name, attr_value in self.__dict__.items():
            table_data.append({"Attribute": attr_name, "Value": repr(attr_value)})
        column_names = ["Attribute", "Value"]
        return table_data, column_names

    def rich_print(self):
        """Display an object as a rich table."""
        table_data, column_names = self._table()
        table = Table(title=f"{self.__class__.__name__} Attributes")
        for column in column_names:
            table.add_column(column, style="bold")

        for row in table_data:
            row_data = [row[column] for column in column_names]
            table.add_row(*row_data)

        return table

    @classmethod
    def example(cls) -> Agent:
        """Return an example agent.

        >>> Agent.example()
        Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5})
        """
        return cls(traits={"age": 22, "hair": "brown", "height": 5.5})

    def code(self) -> str:
        """Return the code for the agent.
        TODO: Add code for dynamic traits function.
        """
        return f"Agent(traits={self.traits})"


def main():
    """
    Give an example of usage.

    WARNING: Consume API credits
    """
    from edsl.agents import Agent
    from edsl.questions import QuestionMultipleChoice

    # a simple agent
    agent = Agent(traits={"age": 10, "hair": "brown", "height": 5.5})
    agent.traits
    agent.print()
    # combining two agents
    agent = Agent(traits={"age": 10}) + Agent(traits={"height": 5.5})
    agent.traits
    # Agent -> Job using the to() method
    agent = Agent(traits={"allergies": "peanut"})
    question = QuestionMultipleChoice(
        question_text="Would you enjoy a PB&J?",
        question_options=["Yes", "No"],
        question_name="food_preference",
    )
    job = agent.to(question)
    # run the job
    results = job.run()
    # results


if __name__ == "__main__":
    #import doctest
    #doctest.testmod()

    a = Agent(traits = {"age": 10}, traits_presentation_template = "I am a {{age}} year old.")
    repr(a.agent_persona)

    a = Agent(traits = {'age': 22, 'hair': 'brown', 'gender': 'female'}, 
        traits_presentation_template = "I am a {{ age }} year-old {{ gender }} with {{ hair }} hair.")
    print(a.agent_persona.render(primary_replacement = a.traits))

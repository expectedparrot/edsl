from __future__ import annotations
import copy
import inspect
import types
import io
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
)

# from edsl.language_models import LanguageModel, LanguageModelOpenAIThreeFiveTurbo
from edsl.language_models.registry import Model
from edsl.scenarios import Scenario
from edsl.utilities import (
    dict_to_html,
    print_dict_as_html_table,
    print_dict_with_rich,
)

from edsl.agents.descriptors import (
    TraitsDescriptor,
    CodebookDescriptor,
    InstructionDescriptor,
)

from edsl.utilities.decorators import sync_wrapper

from edsl.data_transfer_models import AgentResponseDict

from edsl.prompts.library.agent_persona import AgentPersona


class Agent(Base):
    """An agent that can answer questions.

    Parameters
    ----------
    traits : dict, optional - A dictionary of traits that the agent has. The keys need to be
    valid python variable names. The values can be any python object that has a valid __str__ method.
    codebook : dict, optional - A codebook mapping trait keys to trait descriptions.
    instruction : str, optional - Instructions for the agent.

    dynamic_traits_function : Callable, optional - A function that returns a dictionary of traits.

    """

    default_instruction = """You are answering questions as if you were a human. Do not break character."""

    traits = TraitsDescriptor()
    codebook = CodebookDescriptor()
    instruction = InstructionDescriptor()

    def __init__(
        self,
        traits: dict = None,
        codebook: dict = None,
        instruction: str = None,
        trait_presentation_template: str = None,
        dynamic_traits_function: Callable = None,
    ):
        self._traits = traits or dict()
        self.codebook = codebook or dict()
        self.instruction = instruction or self.default_instruction
        self.dynamic_traits_function = dynamic_traits_function
        self._check_dynamic_traits_function()
        self.current_question = None

        if trait_presentation_template is not None:
            self.trait_presentation_template = trait_presentation_template
            self.agent_persona = AgentPersona(text=self.trait_presentation_template)

    def _check_dynamic_traits_function(self):
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
    def traits(self):
        if self.dynamic_traits_function:
            sig = inspect.signature(self.dynamic_traits_function)
            if "question" in sig.parameters:
                return self.dynamic_traits_function(question=self.current_question)
            else:
                return self.dynamic_traits_function()
        else:
            return self._traits

    def add_direct_question_answering_method(self, method: Callable):
        """Adds a method to the agent that can answer a particular question type."""
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

    async def async_answer_question(
        self,
        question: Question,
        scenario: Optional[Scenario] = None,
        model: Optional[LanguageModel] = None,
        debug: bool = False,
        memory_plan: Optional[MemoryPlan] = None,
        current_answers: Optional[dict] = None,
    ):
        """
        This is a function where an agent returns an answer to a particular question.
        However, there are several different ways an agent can answer a question, so the
        actual functionality is delegated to an Invigilator object.
        """
        self.current_question = question
        # model = model or LanguageModelOpenAIThreeFiveTurbo(use_cache=True)
        model = model or Model("gpt-3.5-turbo", use_cache=True)
        scenario = scenario or Scenario()
        invigilator = self._create_invigilator(
            question, scenario, model, debug, memory_plan, current_answers
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
    ):
        model = model or Model("gpt-3.5-turbo", use_cache=True)
        scenario = scenario or Scenario()

        if debug:
            # use the question's simulate_answer method
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
            self, question, scenario, model, memory_plan, current_answers
        )
        return invigilator

    ################
    # Dunder Methods
    ################
    def __add__(self, other_agent: Agent = None) -> Agent:
        """
        Combines two agents by joining their traits.The agents must not have overlapping traits.
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
        """Checks if two agents are equal. Only checks the traits.
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
        return raw_data

    def to_dict(self) -> dict[str, Union[dict, bool]]:
        """Serializes to a dictionary."""
        return self.data

    @classmethod
    def from_dict(cls, agent_dict: dict[str, Union[dict, bool]]) -> Agent:
        """Deserializes from a dictionary."""
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
        """Displays an object as a rich table."""
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
        """Returns an example agent.

        >>> Agent.example()
        Agent(traits = {'age': 22, 'hair': 'brown', 'height': 5.5})
        """
        return cls(traits={"age": 22, "hair": "brown", "height": 5.5})

    def code(self) -> str:
        """Returns the code for the agent."""
        return f"Agent(traits={self.traits})"


def main():
    """Consumes API credits"""
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
    import doctest

    doctest.testmod()

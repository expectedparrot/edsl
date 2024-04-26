"""An Agent is an AI agent that can reference a set of traits in answering questions."""
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

# from edsl.enums import LanguageModelType

from edsl.agents.descriptors import (
    TraitsDescriptor,
    CodebookDescriptor,
    InstructionDescriptor,
    NameDescriptor,
)

from edsl.utilities.decorators import sync_wrapper
from edsl.data_transfer_models import AgentResponseDict
from edsl.prompts.library.agent_persona import AgentPersona

from edsl.data.Cache import Cache


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

        The `traits` parameter is a dictionary of traits that the agent has.
        These traits are used to construct a prompt that is presented to the LLM.
        In the absence of a `traits_presentation_template`, the default is used.
        This is a template that is used to present the agent's traits to the LLM.
        See :py:class:`edsl.prompts.library.agent_persona.AgentPersona` for more information.

        Example usage:

        >>> a = Agent(traits = {"age": 10, "hair": "brown", "height": 5.5})
        >>> a.traits
        {'age': 10, 'hair': 'brown', 'height': 5.5}

        These traits are used to construct a prompt that is presented to the LLM.

        In the absence of a `traits_presentation_template`, the default is used.

        >>> a = Agent(traits = {"age": 10}, traits_presentation_template = "I am a {{age}} year old.")
        >>> repr(a.agent_persona)
        "Prompt(text='I am a {{age}} year old.')"

        When this is rendered for presentation to the LLM, it will replace the `{{age}}` with the actual age.
        it is also possible to use the `codebook` to provide a more human-readable description of the trait.
        Here is an example where we give a prefix to the age trait (namely the age):

        >>> traits = {"age": 10, "hair": "brown", "height": 5.5}
        >>> codebook = {'age': 'Their age is'}
        >>> a = Agent(traits = traits, codebook = codebook, traits_presentation_template = "This agent is Dave. {{codebook['age']}} {{age}}")
        >>> d = a.traits | {'codebook': a.codebook}
        >>> a.agent_persona.render(d)
        Prompt(text='This agent is Dave. Their age is 10')

        Instructions
        ------------------
        The agent can also have instructions. These are instructions that are given to the agent when answering questions.

        >>> Agent.default_instruction
        'You are answering questions as if you were a human. Do not break character.'

        See see how these are used to actually construct the prompt that is presented to the LLM, see :py:class:`edsl.agents.Invigilator.InvigilatorBase`.

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

    def __getitem__(self, key):
        return getattr(self, key)

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
        *,
        question: Question,
        cache,
        scenario: Optional[Scenario] = None,
        model: Optional[LanguageModel] = None,
        debug: bool = False,
        memory_plan: Optional[MemoryPlan] = None,
        current_answers: Optional[dict] = None,
        iteration: int = 1,
        sidecar_model=None,
    ) -> InvigilatorBase:
        """Create an Invigilator.

        An invigator is an object that is responsible for administering a question to an agent and
        recording the responses.
        """
        cache = cache
        self.current_question = question
        model = model or Model()
        scenario = scenario or Scenario()
        invigilator = self._create_invigilator(
            question=question,
            scenario=scenario,
            model=model,
            debug=debug,
            memory_plan=memory_plan,
            current_answers=current_answers,
            iteration=iteration,
            cache=cache,
            sidecar_model=sidecar_model,
        )
        return invigilator

    async def async_answer_question(
        self,
        *,
        question: Question,
        cache,
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
            cache=cache,
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
        cache=None,
        scenario: Optional[Scenario] = None,
        model: Optional[LanguageModel] = None,
        debug: bool = False,
        memory_plan: Optional[MemoryPlan] = None,
        current_answers: Optional[dict] = None,
        iteration: int = 0,
        sidecar_model=None,
    ) -> InvigilatorBase:
        """Create an Invigilator."""
        model = model or Model()
        scenario = scenario or Scenario()

        if cache is None:
            cache = Cache()

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

        if sidecar_model is not None:
            from edsl.agents.Invigilator import InvigilatorSidecar

            invigilator_class = InvigilatorSidecar

        invigilator = invigilator_class(
            self,
            question=question,
            scenario=scenario,
            model=model,
            memory_plan=memory_plan,
            current_answers=current_answers,
            iteration=iteration,
            cache=cache,
            sidecar_model=sidecar_model,
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
        from rich import print_json
        import json

        print_json(json.dumps(self.to_dict()))
        return f"{class_name}({', '.join(items)})"

    def _repr_html_(self):
        from edsl.utilities.utilities import data_to_html

        return data_to_html(self.to_dict())

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
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)

    # a = Agent(
    #     traits={"age": 10}, traits_presentation_template="I am a {{age}} year old."
    # )
    # repr(a.agent_persona)

    # a = Agent(
    #     traits={"age": 22, "hair": "brown", "gender": "female"},
    #     traits_presentation_template="I am a {{ age }} year-old {{ gender }} with {{ hair }} hair.",
    # )
    # print(a.agent_persona.render(primary_replacement=a.traits))

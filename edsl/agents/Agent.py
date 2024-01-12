from __future__ import annotations
import copy
import json
from typing import Any, Callable, Optional, Union, Dict
from abc import ABC, abstractmethod

from edsl.Base import Base

from edsl.exceptions import AgentCombinationError

from edsl.agents.Invigilator import (
    InvigilatorDebug,
    InvigilatorHuman,
    InvigilatorFunctional,
    InvigilatorAI,
)

from edsl.language_models import LanguageModel, LanguageModelOpenAIThreeFiveTurbo
from edsl.scenarios import Scenario
from edsl.utilities import (
    create_valid_var_name,
    dict_to_html,
    print_dict_as_html_table,
    print_dict_with_rich,
)

from edsl.agents.descriptors import (
    TraitsDescriptor,
    CodebookDescriptor,
    InstructionDescriptor,
)


class Agent(Base):
    """An agent answers questions."""

    default_instruction = """You are answering questions as if you were a human. Do not break character."""

    traits = TraitsDescriptor()
    codebook = CodebookDescriptor()
    instruction = InstructionDescriptor()

    def __init__(
        self,
        traits: dict = None,
        codebook: dict = None,
        instruction: str = None,
    ):
        self.traits = traits or dict()
        self.codebook = codebook or dict()
        self.instruction = instruction or self.default_instruction

    def agent_with_valid_trait_names(self) -> Agent:
        """
        DEPRECATED
        """
        print(
            "WARNING: This method is deprecated. We now enforce valid names on Agent creation"
        )
        return self

    def answer_question(
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
        model = model or LanguageModelOpenAIThreeFiveTurbo(use_cache=True)
        scenario = scenario or Scenario()
        # memory_plan = memory_plan
        # current_answers = current_answers or dict()

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
        response = invigilator.answer_question()
        return response

    ################
    # Dunder Methods
    ################
    def __add__(self, other_agent: Agent = None) -> Agent:
        """
        Combines two agents by joining their traits
        - The agents must not have overlapping traits.
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
        """Checks if two agents are equal. Only checks the traits."""
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
    # Forward methods
    ################
    def to(self, question_or_survey) -> Jobs:
        """Sends an agent to a question or survey."""
        from edsl.agents.AgentList import AgentList

        a = AgentList([self])
        return a.to(question_or_survey)

    def get_value(self, jobs: Jobs) -> list[Agent]:
        """Get a list of agents from a Jobs object. Used in Jobs.by()"""
        return jobs.agents

    def set_value(self, jobs: Jobs, new_values: list[Agent]) -> None:
        """Set the Jobs.agents attribute to the new values. Used in Jobs.by()"""
        jobs.agents = new_values

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
    def dict_to_html(self) -> str:
        """Returns the agent's traits as an HTML table."""
        return dict_to_html(self.traits)

    def print(self, html: bool = False, show: bool = False) -> Optional[str]:
        """Prints the agent's traits as a table."""
        if html:
            return print_dict_as_html_table(self.traits, show)
        else:
            print_dict_with_rich(self.traits)

    @classmethod
    def example(cls) -> Agent:
        """Returns an example agent."""
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
    main()

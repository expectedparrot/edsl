from __future__ import annotations
import copy
import json
from typing import Any, Callable, Optional, Union
from edsl.exceptions import (
    AgentAttributeLookupCallbackError,
    AgentCombinationError,
    AgentRespondedWithBadJSONError,
)
from edsl.language_models import LanguageModel, LanguageModelOpenAIThreeFiveTurbo
from edsl.scenarios import Scenario
from edsl.utilities import (
    create_valid_var_name,
    dict_to_html,
    print_dict_as_html_table,
    print_dict_with_rich,
)


DEFAULT_INSTRUCTION = (
    """You are answering questions as if you were a human. Do not break character."""
)


class Agent:
    """An agent answers."""

    def __init__(
        self,
        traits: dict = None,
        attribute_lookup_callback: Callable = None,
        verbose: bool = False,
        original_names_dict: dict = None,
        instruction: str = None,
    ):
        self.attribute_lookup_callback = attribute_lookup_callback
        self.instruction = instruction or DEFAULT_INSTRUCTION
        self.verbose = verbose
        self._original_names = original_names_dict or dict()
        self._questions_to_traits = dict()
        self._traits = traits or dict()

    ################
    # TRAITS METHODS
    ################
    @property
    def traits(self) -> dict[str, Any]:
        """Returns the traits of the agent."""
        return self._traits

    def update_traits(
        self,
        new_attributes: list[str],
        attribute_lookup_callback: Callable = None,
    ) -> None:
        """Updates the Agent traits with new attributes. Allows an optional callback, defaulting to the instance's attribute_lookup_callback."""
        attribute_lookup = attribute_lookup_callback or self.attribute_lookup_callback
        if not attribute_lookup:
            raise AgentAttributeLookupCallbackError("Missing callback.")

        _traits = {}
        for attribute in new_attributes:
            try:
                trait_name, value = attribute_lookup(attribute)
                _traits[trait_name] = value
            except Exception as e:
                raise AgentAttributeLookupCallbackError(
                    f"Error in attribute lookup callback: {e}"
                    f"Attribute Lookup Callback: {attribute_lookup}"
                    f"Attribute: {attribute}"
                )
        self._traits = _traits

    def get_original_name(self, trait: str) -> str:
        """Returns the original name of a trait, if any."""
        return self._original_names.get(trait, trait)

    def agent_with_valid_trait_names(self) -> Agent:
        """
        Returns a new agent with trait keys that are valid variable names.
        Useful down the road; stores the original names.
        """
        original_names_dict = {}
        new_traits_dict = {}
        for key, value in self._traits.items():
            new_name = create_valid_var_name(key)
            new_traits_dict[new_name] = value
            original_names_dict[new_name] = key

        return Agent(traits=new_traits_dict, original_names_dict=original_names_dict)

    ################
    # LLM METHODS
    ################
    def construct_system_prompt(self) -> str:
        """Constructs the system prompt for the LLM call."""
        instruction = self.instruction
        traits = f"Your traits are: {self.traits}."
        return f"{instruction} {traits}"

    def get_response(
        self, prompt: str, system_prompt: str, model: LanguageModel = None
    ):
        """Calls the LLM and gets a response. Used in the `answer_question` method."""
        model = model or LanguageModelOpenAIThreeFiveTurbo(use_cache=True)

        try:
            response = model.get_response(prompt, system_prompt)
        except json.JSONDecodeError as e:
            raise AgentRespondedWithBadJSONError(
                f"Returned bad JSON: {e}"
                f"Prompt: {prompt}"
                f"System Prompt: {system_prompt}"
            )

        return response

    def answer_question(
        self,
        question: Question,
        scenario: Optional[Scenario] = None,
        model: Optional[LanguageModel] = None,
        debug: bool = False,
    ):
        """
        The main function that the agent calls to answer a question.
        1) It first constructs the prompts, then calls the LLM.
        2) It then validates the response and the answers.
        The answer from the JSON can be in code, so it uses the
        question-specific translation function to translate the code to the answer.
        """
        # simulated answers (w/o API call)
        #  if debug mode
        if debug:
            return question.simulate_answer(human_readable=True)
        #  if the question has this method
        if hasattr(question, "answer_question_directly"):
            return question.answer_question_directly(
                scenario=scenario, agent_traits=self.traits
            )
        #  if the agent has this method
        if hasattr(self, "answer_question_directly"):
            answer = self.answer_question_directly(question.question_name)
            response = {"answer": answer}
            response = question.validate_response(response)
            response["model"] = "human"
            response["scenario"] = scenario
            return response

        # actual answers (w/ API call)
        #  get answer
        scenario = scenario or Scenario()
        system_prompt = self.construct_system_prompt()
        prompt = question.get_prompt(scenario)
        response = self.get_response(prompt, system_prompt, model)
        #  validate answer
        response = question.validate_response(response)
        response = question.validate_answer(response)
        answer_code = response["answer"]
        response["answer"] = question.translate_answer_code_to_answer(
            answer_code, scenario
        )
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
        return self.traits == other.traits

    def __repr__(self) -> str:
        """Returns the agent's representation."""
        return f"Agent(traits = {self.traits})"

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
    def to_dict(self) -> dict[str, Union[dict, bool]]:
        """Serializes to a dictionary."""
        return {"traits": self.traits, "verbose": self.verbose}

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

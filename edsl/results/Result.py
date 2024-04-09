# """This module contains the Result class, which captures the result of one interview."""
from __future__ import annotations
from collections import UserDict
from typing import Any, Type

from rich.table import Table

from IPython.display import display

from edsl.agents import Agent
from edsl.language_models import LanguageModel
from edsl.scenarios import Scenario

from edsl.utilities import is_notebook

from edsl.Base import Base

from collections import UserDict


class PromptDict(UserDict):
    """A dictionary that is used to store the prompt for a given result."""

    def rich_print(self):
        """Display an object as a table."""
        table = Table(title="")
        table.add_column("Attribute", style="bold")
        table.add_column("Value")

        to_display = self
        for attr_name, attr_value in to_display.items():
            table.add_row(attr_name, repr(attr_value))

        return table


def agent_namer_closure():
    """Return a function that can be used to name an agent."""
    agent_dict = {}

    def agent_namer(agent):
        """Return a name for an agent. If the agent has been named before, return the same name. Otherwise, return a new name."""
        nonlocal agent_dict
        agent_count = len(agent_dict)
        if id(agent) in agent_dict:
            return agent_dict[id(agent)]
        else:
            agent_dict[id(agent)] = f"Agent_{agent_count}"
            return agent_dict[id(agent)]

    return agent_namer


agent_namer = agent_namer_closure()


class Result(Base, UserDict):
    """
    This class captures the result of one interview.

    The answer dictionary has the structure:

    >>> Result.example().answer
    {'how_feeling': 'OK', 'how_feeling_comment': 'This is a real survey response from a human.', 'how_feeling_yesterday': 'Great', 'how_feeling_yesterday_comment': 'This is a real survey response from a human.'}

    Its main data is an Agent, a Scenario, a Model, an Iteration, and an Answer.
    These are stored both in the UserDict and as attributes.

    >>> results.select('question_text.how_feeling')
    >>> results.select('question_type.how_feeling')

    """

    def __init__(
        self,
        agent: Agent,
        scenario: Scenario,
        model: Type[LanguageModel],
        iteration: int,
        answer: str,
        prompt: dict[str, str] = None,
        raw_model_response=None,
        survey=None,
    ):
        """Initialize a Result object.

        :param agent: The Agent object.
        :param scenario: The Scenario object.
        :param model: The LanguageModel object.
        :param iteration: The iteration number.
        :param answer: The answer string.
        :param prompt: A dictionary of prompts.
        :param raw_model_response: The raw model response.

        """
        data = {
            "agent": agent,
            "scenario": scenario,
            "model": model,
            "iteration": iteration,
            "answer": answer,
            "prompt": prompt or {},
            "raw_model_response": raw_model_response or {},
        }
        super().__init__(**data)
        # but also store the data as attributes
        self.agent = agent
        self.scenario = scenario
        self.model = model
        self.iteration = iteration
        self.answer = answer
        self.prompt = prompt or {}
        self.raw_model_response = raw_model_response or {}
        self.survey = survey

        if survey is not None:
            self.question_to_attributes = {
                q.question_name: {
                    "question_text": q.question_text,
                    "question_type": q.question_type,
                }
                for q in survey.questions
            }
        else:
            self.question_to_attributes = {}

    ###############
    # Used in Results
    ###############
    @property
    def sub_dicts(self) -> dict[str, dict]:
        """Return a dictionary where keys are strings for each of the main class attributes/objects."""
        if self.agent.name is None:
            agent_name = agent_namer(self.agent)
        else:
            agent_name = self.agent.name

        question_text_dict = {}
        for key, _ in self.answer.items():
            if key in self.question_to_attributes:
                question_text_dict[
                    key + "_question_text"
                ] = self.question_to_attributes[key]["question_text"]

        return {
            "agent": self.agent.traits | {"agent_name": agent_name},
            "scenario": self.scenario,
            "model": self.model.parameters | {"model": self.model.model},
            "answer": self.answer,
            "prompt": self.prompt,
            "raw_model_response": self.raw_model_response,
            "iteration": {"iteration": self.iteration},
            "question_text": question_text_dict,
        }

    def code(self):
        """Return a string of code that can be used to recreate the Result object."""
        raise NotImplementedError

    @property
    def combined_dict(self) -> dict[str, Any]:
        """Return a dictionary that includes all sub_dicts, but also puts the key-value pairs in each sub_dict as a key_value pair in the combined dictionary."""
        combined = {}
        for key, sub_dict in self.sub_dicts.items():
            combined.update(sub_dict)
            combined.update({key: sub_dict})
        return combined

    def get_value(self, data_type: str, key: str) -> Any:
        """Return the value for a given data type and key.

        - data types can be "agent", "scenario", "model", or "answer"
        - keys are relevant attributes of the Objects the data types represent
        results.get_value("answer", "how_feeling") will return "Good" or "Bad" or whatnot
        """
        return self.sub_dicts[data_type][key]

    @property
    def key_to_data_type(self) -> dict[str, str]:
        """Return a dictionary where keys are object attributes and values are the data type (object) that the attribute is associated with."""
        d = {}
        for data_type in [
            "agent",
            "scenario",
            "model",
            "answer",
            "prompt",
            "raw_model_response",
            "iteration",
        ]:
            for key in self.sub_dicts[data_type]:
                d[key] = data_type
        return d

    def rows(self, index):
        """Return a generator of rows for the Result object."""
        for data_type, subdict in self.sub_dicts.items():
            for key, value in subdict.items():
                yield (index, data_type, key, str(value))

    ###############
    # Useful
    ###############
    def copy(self) -> Result:
        """Return a copy of the Result object."""
        return Result.from_dict(self.to_dict())

    def __eq__(self, other):
        """Return True if the Result object is equal to another Result object."""
        return self.to_dict() == other.to_dict()

    ###############
    # Serialization
    ###############
    def to_dict(self) -> dict[str, Any]:
        """Return a dictionary representation of the Result object."""
        return {
            k: v if not hasattr(v, "to_dict") else v.to_dict() for k, v in self.items()
        }

    @classmethod
    def from_dict(self, json_dict: dict) -> Result:
        """Return a Result object from a dictionary representation."""
        result = Result(
            agent=Agent.from_dict(json_dict["agent"]),
            scenario=Scenario.from_dict(json_dict["scenario"]),
            model=LanguageModel.from_dict(json_dict["model"]),
            iteration=json_dict["iteration"],
            answer=json_dict["answer"],
            prompt=json_dict["prompt"],
            raw_model_response=json_dict.get(
                "raw_model_response", {"raw_model_response": "No raw model response"}
            ),
        )
        return result

    def rich_print(self):
        """Display an object as a table."""
        # from edsl.utilities import print_dict_with_rich
        from rich import print

        table = Table(title="Result")
        table.add_column("Attribute", style="bold")
        table.add_column("Value")

        to_display = self.__dict__.copy()
        data = to_display.pop("data", None)
        for attr_name, attr_value in to_display.items():
            if hasattr(attr_value, "rich_print"):
                table.add_row(attr_name, attr_value.rich_print())
            elif isinstance(attr_value, dict):
                a = PromptDict(attr_value)
                table.add_row(attr_name, a.rich_print())
            else:
                table.add_row(attr_name, repr(attr_value))
        return table

    def __repr__(self):
        """Return a string representation of the Result object."""
        return f"Result(agent={repr(self.agent)}, scenario={repr(self.scenario)}, model={repr(self.model)}, iteration={self.iteration}, answer={repr(self.answer)}, prompt={repr(self.prompt)}"

    @classmethod
    def example(cls):
        """Return an example Result object."""
        from edsl.results import Results

        return Results.example()[0]


def main():
    """Run the main function."""
    from edsl.results.Result import Result
    import json

    print("Being imported")
    json_string = """
    {
        "agent": {
            "traits": {
                "status": "Unhappy"
            }
        },
        "scenario": {
            "period": "morning"
        },
        "model": {
            "model": "gpt-3.5-turbo",
            "parameters": {
                "temperature": 0.5,
                "max_tokens": 1000,
                "top_p": 1,
                "frequency_penalty": 0,
                "presence_penalty": 0,
                "use_cache": true
            }
        },
        "iteration": 0,
        "answer": {
            "how_feeling": "Bad"
        }, 
        "prompt": {"how_feeling_user_prompt": "How are you feeling today?", "how_feeling_system_prompt": "Answer the question"}
    }
    """

    result = Result.from_dict(json.loads(json_string))

    result.sub_dicts
    assert result.combined_dict["how_feeling"] == "Bad"

    result.combined_dict
    assert result.get_value("answer", "how_feeling") == "Bad"

    result.key_to_data_type
    print(result)

    assert result == result.copy()

    result.to_dict()


if __name__ == "__main__":
    print(Result.example())

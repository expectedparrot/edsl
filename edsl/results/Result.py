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
    def rich_print(self):
        """Displays an object as a table."""
        table = Table(title="")
        table.add_column("Attribute", style="bold")
        table.add_column("Value")

        to_display = self
        for attr_name, attr_value in to_display.items():
            table.add_row(attr_name, repr(attr_value))

        return table


def agent_namer_closure():
    """Returns a function that can be used to name an agent."""
    agent_dict = {}

    def agent_namer(agent):
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
    - Its main data is an Agent, a Scenario, a Model, an Iteration, and an Answer.
    - These are stored both in the UserDict and as attributes.
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
    ):
        # initialize the UserDict
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

    ###############
    # Used in Results
    ###############
    @property
    def sub_dicts(self) -> dict[str, dict]:
        """Returns a dictionary where keys are strings for each of the main class attributes/objects (except for iteration) and values are dictionaries for the attributes and values for each of these objects."""

        if self.agent.name is None:
            agent_name = agent_namer(self.agent)
        else:
            agent_name = self.agent.name

        return {
            "agent": self.agent.traits | {"agent_name": agent_name},
            "scenario": self.scenario,
            "model": self.model.parameters | {"model": self.model.model},
            "answer": self.answer,
            "prompt": self.prompt,
            "raw_model_response": self.raw_model_response,
        }

    def code(self):
        raise NotImplementedError

    @property
    def combined_dict(self) -> dict[str, Any]:
        """Returns a dictionary that includes all sub_dicts, but also puts the key-value pairs in each sub_dict as a key_value pair in the combined dictionary."""
        combined = {}
        for key, sub_dict in self.sub_dicts.items():
            combined.update(sub_dict)
            combined.update({key: sub_dict})
        return combined

    def get_value(self, data_type: str, key: str) -> Any:
        """Returns the value for a given data type and key
        - data types can be "agent", "scenario", "model", or "answer"
        - keys are relevant attributes of the Objects the data types represent
        results.get_value("answer", "how_feeling") will return "Good" or "Bad" or whatnot
        """
        return self.sub_dicts[data_type][key]

    @property
    def key_to_data_type(self) -> dict[str, str]:
        """Returns a dictionary where keys are object attributes and values are the data type (object) that the attribute is associated with."""
        d = {}
        for data_type in [
            "agent",
            "scenario",
            "model",
            "answer",
            "prompt",
            "raw_model_response",
        ]:
            for key in self.sub_dicts[data_type]:
                d[key] = data_type
        return d

    def rows(self, index):
        for data_type, subdict in self.sub_dicts.items():
            for key, value in subdict.items():
                yield (index, data_type, key, str(value))

    ###############
    # Useful
    ###############
    def copy(self) -> Result:
        """Returns a copy of the Result object."""
        return Result.from_dict(self.to_dict())

    def __eq__(self, other):
        return self.to_dict() == other.to_dict()

    ###############
    # Serialization
    ###############
    def to_dict(self) -> dict[str, Any]:
        """Returns a dictionary representation of the Result object."""
        return {
            k: v if not hasattr(v, "to_dict") else v.to_dict() for k, v in self.items()
        }

    @classmethod
    def from_dict(self, json_dict: dict) -> Result:
        """Returns a Result object from a dictionary representation."""
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
        """Displays an object as a table."""
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
        return f"Result(agent={repr(self.agent)}, scenario={repr(self.scenario)}, model={repr(self.model)}, iteration={self.iteration}, answer={repr(self.answer)}, prompt={repr(self.prompt)}"

    @classmethod
    def example(cls):
        from edsl.results import Results

        return Results.example()[0]


def main():
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

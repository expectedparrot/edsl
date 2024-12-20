# """This module contains the Result class, which captures the result of one interview."""
from __future__ import annotations
import inspect
from collections import UserDict
from typing import Any, Type, Callable, Optional, TYPE_CHECKING, Union
from edsl.Base import Base
from edsl.utilities.decorators import add_edsl_version, remove_edsl_version

if TYPE_CHECKING:
    from edsl.agents.Agent import Agent
    from edsl.scenarios.Scenario import Scenario
    from edsl.language_models.LanguageModel import LanguageModel
    from edsl.prompts.Prompt import Prompt
    from edsl.surveys.Survey import Survey


QuestionName = str
AnswerValue = Any


class AgentNamer:
    """Maintains a registry of agent names to ensure unique naming."""

    def __init__(self):
        self._registry = {}

    def get_name(self, agent: "Agent") -> str:
        """Get or create a unique name for an agent."""
        agent_id = id(agent)
        if agent_id not in self._registry:
            self._registry[agent_id] = f"Agent_{len(self._registry)}"
        return self._registry[agent_id]


# Global instance for agent naming
agent_namer = AgentNamer().get_name


class Result(Base, UserDict):
    """
    This class captures the result of one interview.
    """

    def __init__(
        self,
        agent: "Agent",
        scenario: "Scenario",
        model: "LanguageModel",
        iteration: int,
        answer: dict[QuestionName, AnswerValue],
        prompt: dict[QuestionName, str] = None,
        raw_model_response: Optional[dict] = None,
        survey: Optional["Survey"] = None,
        question_to_attributes: Optional[dict[QuestionName, Any]] = None,
        generated_tokens: Optional[dict] = None,
        comments_dict: Optional[dict] = None,
        cache_used_dict: Optional[dict[QuestionName, bool]] = None,
        indices: Optional[dict] = None,
    ):
        """Initialize a Result object.

        :param agent: The Agent object.
        :param scenario: The Scenario object.
        :param model: The LanguageModel object.
        :param iteration: The iteration number.
        :param answer: The answer string.
        :param prompt: A dictionary of prompts.
        :param raw_model_response: The raw model response.
        :param survey: The Survey object.
        :param question_to_attributes: A dictionary of question attributes.
        :param generated_tokens: A dictionary of generated tokens.
        :param comments_dict: A dictionary of comments.
        :param cache_used_dict: A dictionary of cache usage.
        :param indices: A dictionary of indices.

        """
        self.question_to_attributes = (
            question_to_attributes or self._create_question_to_attributes(survey)
        )

        data = {
            "agent": agent,
            "scenario": scenario,
            "model": model,
            "iteration": iteration,
            "answer": answer,
            "prompt": prompt or {},
            "raw_model_response": raw_model_response or {},
            "question_to_attributes": question_to_attributes,
            "generated_tokens": generated_tokens or {},
            "comments_dict": comments_dict or {},
            "cache_used_dict": cache_used_dict or {},
        }
        super().__init__(**data)
        self.indices = indices
        self._sub_dicts = self._construct_sub_dicts()
        (
            self._combined_dict,
            self._problem_keys,
        ) = self._compute_combined_dict_and_problem_keys()

    @staticmethod
    def _create_question_to_attributes(survey):
        """Create a dictionary of question attributes."""
        if survey is None:
            return {}
        return {
            q.question_name: {
                "question_text": q.question_text,
                "question_type": q.question_type,
                "question_options": (
                    None if not hasattr(q, "question_options") else q.question_options
                ),
            }
            for q in survey.questions
        }

    @property
    def agent(self) -> "Agent":
        """Return the Agent object."""
        return self.data["agent"]

    @property
    def scenario(self) -> "Scenario":
        """Return the Scenario object."""
        return self.data["scenario"]

    @property
    def model(self) -> "LanguageModel":
        """Return the LanguageModel object."""
        return self.data["model"]

    @property
    def answer(self) -> dict[QuestionName, AnswerValue]:
        """Return the answers."""
        return self.data["answer"]

    @staticmethod
    def _create_agent_sub_dict(agent) -> dict:
        """Create a dictionary of agent details"""
        if agent.name is None:
            agent_name = agent_namer(agent)
        else:
            agent_name = agent.name

        return {
            "agent": agent.traits
            | {"agent_name": agent_name}
            | {"agent_instruction": agent.instruction},
        }

    @staticmethod
    def _create_model_sub_dict(model) -> dict:
        return {
            "model": model.parameters | {"model": model.model},
        }

    @staticmethod
    def _iteration_sub_dict(iteration) -> dict:
        return {
            "iteration": {"iteration": iteration},
        }

    def _construct_sub_dicts(self) -> dict[str, dict]:
        """Construct a dictionary of sub-dictionaries for the Result object."""
        sub_dicts_needing_new_keys = {
            "question_text": {},
            "question_options": {},
            "question_type": {},
        }

        for question_name in self.data["answer"]:
            if question_name in self.question_to_attributes:
                for dictionary_name in sub_dicts_needing_new_keys:
                    new_key = question_name + "_" + dictionary_name
                    sub_dicts_needing_new_keys[dictionary_name][
                        new_key
                    ] = self.question_to_attributes[question_name][dictionary_name]

        new_cache_dict = {
            f"{k}_cache_used": v for k, v in self.data["cache_used_dict"].items()
        }

        d = {
            **self._create_agent_sub_dict(self.data["agent"]),
            **self._create_model_sub_dict(self.data["model"]),
            **self._iteration_sub_dict(self.data["iteration"]),
            "scenario": self.data["scenario"],
            "answer": self.data["answer"],
            "prompt": self.data["prompt"],
            "comment": self.data["comments_dict"],
            "generated_tokens": self.data["generated_tokens"],
            "raw_model_response": self.data["raw_model_response"],
            "question_text": sub_dicts_needing_new_keys["question_text"],
            "question_options": sub_dicts_needing_new_keys["question_options"],
            "question_type": sub_dicts_needing_new_keys["question_type"],
            "cache_used": new_cache_dict,
        }
        if hasattr(self, "indices") and self.indices is not None:
            d["agent"].update({"agent_index": self.indices["agent"]})
            d["scenario"].update({"scenario_index": self.indices["scenario"]})
            d["model"].update({"model_index": self.indices["model"]})
        return d

    @property
    def sub_dicts(self) -> dict[str, dict]:
        """Return a dictionary where keys are strings for each of the main class attributes/objects."""
        if self._sub_dicts is None:
            self._sub_dicts = self._construct_sub_dicts()
        return self._sub_dicts

    def check_expression(self, expression: str) -> None:
        for key in self.problem_keys:
            if key in expression and not key + "." in expression:
                raise ValueError(
                    f"Key by iself {key} is problematic. Use the full key {key + '.' + key} name instead."
                )
        return None

    def code(self):
        """Return a string of code that can be used to recreate the Result object."""
        raise NotImplementedError

    @property
    def problem_keys(self) -> list[str]:
        """Return a list of keys that are problematic."""
        return self._problem_keys

    def _compute_combined_dict_and_problem_keys(
        self,
    ) -> tuple[dict[str, Any], list[str]]:
        combined = {}
        problem_keys = []
        for key, sub_dict in self.sub_dicts.items():
            combined.update(sub_dict)
            # in some cases, the sub_dict might have keys that conflict with the main dict
            if key in combined:
                # The key is already in the combined dict
                problem_keys = problem_keys + [key]

            combined.update({key: sub_dict})
            # I *think* this allows us to do do things like "answer.how_feelling" i.e., that the evaluator can use
            # dot notation to access the subdicts.
        return combined, problem_keys

    @property
    def combined_dict(self) -> dict[str, Any]:
        """Return a dictionary that includes all sub_dicts, but also puts the key-value pairs in each sub_dict as a key_value pair in the combined dictionary.

        >>> r = Result.example()
        >>> r.combined_dict['how_feeling']
        'OK'
        """
        if self._combined_dict is None or self._problem_keys is None:
            (
                self._combined_dict,
                self._problem_keys,
            ) = self._compute_combined_dict_and_problem_keys()
        return self._combined_dict

    @property
    def problem_keys(self) -> list[str]:
        """Return a list of keys that are problematic."""
        if self._combined_dict is None or self._problem_keys is None:
            self._compute_combined_dict_and_problem_keys()
        return self._problem_keys

    def get_value(self, data_type: str, key: str) -> Any:
        """Return the value for a given data type and key.

        >>> r = Result.example()
        >>> r.get_value("answer", "how_feeling")
        'OK'

        - data types can be "agent", "scenario", "model", or "answer"
        - keys are relevant attributes of the Objects the data types represent
        """
        return self.sub_dicts[data_type][key]

    @property
    def key_to_data_type(self) -> dict[str, str]:
        """Return a dictionary where keys are object attributes and values are the data type (object) that the attribute is associated with.

        >>> r = Result.example()
        >>> r.key_to_data_type["how_feeling"]
        'answer'

        """
        d = {}
        problem_keys = []
        data_types = sorted(self.sub_dicts.keys())
        for data_type in data_types:
            for key in self.sub_dicts[data_type]:
                if key in d:
                    import warnings

                    warnings.warn(
                        f"Key '{key}' of data type '{data_type}' is already in use. Renaming to {key}_{data_type}"
                    )
                    problem_keys.append((key, data_type))
                    key = f"{key}_{data_type}"
                d[key] = data_type

        for key, data_type in problem_keys:
            self.sub_dicts[data_type][f"{key}_{data_type}"] = self.sub_dicts[
                data_type
            ].pop(key)
        return d

    def copy(self) -> Result:
        """Return a copy of the Result object.

        >>> r = Result.example()
        >>> r2 = r.copy()
        >>> r == r2
        True
        >>> id(r) == id(r2)
        False
        """
        return Result.from_dict(self.to_dict())

    def __eq__(self, other) -> bool:
        """Return True if the Result object is equal to another Result object.

        >>> r = Result.example()
        >>> r == r
        True

        """
        return hash(self) == hash(other)

    def to_dict(
        self, add_edsl_version: bool = True, include_cache_info: bool = False
    ) -> dict[str, Any]:
        """Return a dictionary representation of the Result object.

        >>> r = Result.example()
        >>> r.to_dict()['scenario']
        {'period': 'morning', 'scenario_index': 0, 'edsl_version': '...', 'edsl_class_name': 'Scenario'}
        """

        def convert_value(value, add_edsl_version=True):
            if hasattr(value, "to_dict"):
                return value.to_dict(add_edsl_version=add_edsl_version)
            else:
                return value

        d = {}
        for key, value in self.items():
            d[key] = convert_value(value, add_edsl_version=add_edsl_version)

            if key == "prompt":
                new_prompt_dict = {}
                for prompt_name, prompt_obj in value.items():
                    new_prompt_dict[prompt_name] = (
                        prompt_obj
                        if not hasattr(prompt_obj, "to_dict")
                        else prompt_obj.to_dict()
                    )
                d[key] = new_prompt_dict
        if add_edsl_version:
            from edsl import __version__

            d["edsl_version"] = __version__
            d["edsl_class_name"] = "Result"

        if include_cache_info:
            d["cache_used_dict"] = self.data["cache_used_dict"]
        else:
            d.pop("cache_used_dict", None)

        return d

    def __hash__(self):
        """Return a hash of the Result object."""
        from edsl.utilities.utilities import dict_hash

        return dict_hash(self.to_dict(add_edsl_version=False, include_cache_info=False))

    @classmethod
    @remove_edsl_version
    def from_dict(self, json_dict: dict) -> Result:
        """Return a Result object from a dictionary representation."""

        from edsl.agents.Agent import Agent
        from edsl.scenarios.Scenario import Scenario
        from edsl.language_models.LanguageModel import LanguageModel
        from edsl.prompts.Prompt import Prompt

        prompt_data = json_dict.get("prompt", {})
        prompt_d = {}
        for prompt_name, prompt_obj in prompt_data.items():
            prompt_d[prompt_name] = Prompt.from_dict(prompt_obj)

        result = Result(
            agent=Agent.from_dict(json_dict["agent"]),
            scenario=Scenario.from_dict(json_dict["scenario"]),
            model=LanguageModel.from_dict(json_dict["model"]),
            iteration=json_dict["iteration"],
            answer=json_dict["answer"],
            prompt=prompt_d,  # json_dict["prompt"],
            raw_model_response=json_dict.get(
                "raw_model_response", {"raw_model_response": "No raw model response"}
            ),
            question_to_attributes=json_dict.get("question_to_attributes", None),
            generated_tokens=json_dict.get("generated_tokens", {}),
            comments_dict=json_dict.get("comments_dict", {}),
            cache_used_dict=json_dict.get("cache_used_dict", {}),
        )
        return result

    def __repr__(self):
        """Return a string representation of the Result object."""
        params = ", ".join(f"{key}={repr(value)}" for key, value in self.data.items())
        return f"{self.__class__.__name__}({params})"

    @classmethod
    def example(cls):
        """Return an example Result object.

        >>> Result.example()
        Result(...)

        """
        from edsl.results.Results import Results

        return Results.example()[0]

    def score(self, scoring_function: Callable) -> Union[int, float]:
        """Score the result using a passed-in scoring function.

        >>> def f(status): return 1 if status == 'Joyful' else 0
        >>> Result.example().score(f)
        1
        """
        signature = inspect.signature(scoring_function)
        params = {}
        for k, v in signature.parameters.items():
            if k in self.combined_dict:
                params[k] = self.combined_dict[k]
            elif v.default is not v.empty:
                params[k] = v.default
            else:
                raise ValueError(f"Parameter {k} not found in Result object")
        return scoring_function(**params)


if __name__ == "__main__":
    import doctest

    doctest.testmod(optionflags=doctest.ELLIPSIS)

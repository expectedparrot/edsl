from collections import UserDict
from typing import Type
from edsl.agents import Agent
from edsl.scenarios import Scenario
from edsl.language_models import LanguageModel


class Result(UserDict):
    """Represents the result of an interview: one survey, one agent, one scenario,
    one model, one iteration, and one result."""

    def __init__(
        self,
        agent: Agent,
        scenario: Scenario,
        model: Type[LanguageModel],
        iteration: int,
        answer: str,
    ):
        data = {
            "agent": agent.agent_with_valid_trait_names(),
            "scenario": scenario,
            "model": model,
            "iteration": iteration,
            "answer": answer,
        }
        super().__init__(**data)

        self.agent = agent
        self.scenario = scenario
        self.model = model
        self.iteration = iteration
        self.answer = answer

        ## TODO: Dictionary representations
        self.sub_dicts = {
            "answer": answer,
            "scenario": scenario,
            # "agent": agent.traits,
            "agent": agent.agent_with_valid_trait_names().traits,
            "model": model.parameters | {"model": model.model},
        }

        self.combined_dict = {}
        for key in self.sub_dicts:
            self.combined_dict.update(self.sub_dicts[key])
            self.combined_dict.update({key: self.sub_dicts[key]})

    def get_value(self, data_type, key):
        """Returns the value for a given key and data type e.g.,
        results.get_value("answer", "how_feeling") will return "Good" or "Bad" or whatnot
        """
        return self.sub_dicts[data_type][key]

    @property
    def key_to_data_type(self):
        d = {}
        for data_type in ["agent", "scenario", "model", "answer"]:
            for key in self.sub_dicts[data_type]:
                d[key] = data_type
        return d

    def __repr__(self):
        return f"Result(agent={self.agent}, scenario={self.scenario}, model={self.model}, iteration={self.iteration}, answer={self.answer})"

    def to_dict(self):
        return {
            k: v if not hasattr(v, "to_dict") else v.to_dict() for k, v in self.items()
        }

    def copy(self):
        return Result.from_dict(self.to_dict())

    @classmethod
    def from_dict(self, json_dict):
        result = Result(
            agent=Agent.from_dict(json_dict["agent"]),
            scenario=Scenario.from_dict(json_dict["scenario"]),
            model=LanguageModel.from_dict(json_dict["model"]),
            iteration=json_dict["iteration"],
            answer=json_dict["answer"],
        )
        return result


if __name__ == "__main__":
    import json

    print("Being imported")
    json_string = """
    {
    "survey": {
        "questions": [
            {
                "question_name": "how_feeling",
                "question_text": "How are you this {{ period }}?",
                "question_options": [
                    "Good",
                    "Great",
                    "OK",
                    "Bad"
                ],
                "type": "multiple_choice"
            }
        ],
        "name": null,
        "rule_collection": [
            {
                "current_q": 0,
                "expression": "True",
                "next_q": 1,
                "priority": -1,
                "question_name_to_index": {
                    "how_feeling": 0
                }
            }
        ]
    },
    "agent": {
        "traits": {
            "status": "Unhappy"
        },
        "verbose": false
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
        },
    },
    "iteration": 0,
    "answer": {
        "how_feeling": "Bad"
    }
    }
    """
    result = Result.from_dict(json.loads(json_string))

    # get combined dict working
    assert result.combined_dict["how_feeling"] == "Bad"
    assert result.get_value("answer", "how_feeling") == "Bad"

    # assert(result.get_value())

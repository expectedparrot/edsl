from collections import UserDict


class Result(UserDict):
    """Represents the result of an interview: one survey, one agent, one scenario,
    one model, one iteration, and one result."""

    def __init__(self, survey, agent, scenario, model, iteration, answer):
        # instantiates the UserDict with the actual objects
        data = {
            #            "survey": survey,
            "survey": None,
            "agent": agent.agent_with_valid_trait_names(),
            "scenario": scenario,
            "model": model,
            "iteration": iteration,
            "answer": answer,
        }

        super().__init__(**data)

        # Also assign the attributes to the class for convenience

        # TODO: This actually isn't expensive in terms of memory
        # for key, value in data.items():
        #    setattr(self, key, value)
        self.agent = agent

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
        survey = self.survey if hasattr(self, "survey") else None
        return f"Result(survey={survey}, agent={self.agent}, scenario={self.scenario}, model={self.model}, iteration={self.iteration}, answer={self.answer})"

    def to_dict(self):
        return {
            k: v if not hasattr(v, "to_dict") else v.to_dict() for k, v in self.items()
        }

    @classmethod
    def from_dict(self, json_dict):
        from edsl.agents import Agent
        from edsl.scenarios import Scenario
        from edsl.language_models import LanguageModel

        return Result(
            # survey=Survey.from_dict(json_dict["survey"]),
            survey=None,
            agent=Agent.from_dict(json_dict["agent"]),
            scenario=Scenario.from_dict(json_dict["scenario"]),
            model=LanguageModel.from_dict(json_dict["model"]),
            iteration=json_dict["iteration"],
            answer=json_dict["answer"],
        )

    @property
    def agents(self):
        return [r.agent for r in self]


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

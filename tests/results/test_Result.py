import pytest

from edsl.results import Result
from edsl.agents import Agent
from edsl.scenarios import Scenario
from edsl.language_models.LanguageModel import LanguageModel


def test_constructor():
    result = Result(
        agent=Agent.example(),
        scenario=Scenario.example(),
        model=LanguageModel.example(),
        iteration=1,
        answer={"how_feeling": "Good"},
        prompt={"key": "value"},
    )

    agent_traits = Agent.example().traits
    agent_traits["agent_name"] = "Agent_0"

    try:
        assert agent_traits.items() <= result.sub_dicts["agent"].items()
    except:
        print(result.sub_dicts["agent"])
        print(agent_traits)
        breakpoint()


def test_constructor():
    result = Result(
        agent=Agent(name="Arsenio Billingham", traits={"show_status": "off the air"}),
        scenario=Scenario.example(),
        model=LanguageModel.example(),
        iteration=1,
        answer={"how_feeling": "Good"},
        prompt={"key": "value"},
    )

    assert {
        "agent_name": "Arsenio Billingham",
        "show_status": "off the air",
    }.items() <= result.sub_dicts["agent"].items()

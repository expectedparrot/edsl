from edsl.results.Result import main


# def test_result_main():
#     main()


from edsl.results.Result import Result

from edsl import Agent
from edsl import Scenario
from edsl.language_models import LanguageModel


def test_constructor():
    result = Result(
        agent=Agent.example(),
        scenario=Scenario.example(),
        model=LanguageModel.example(),
        iteration=1,
        answer={'how_feeling': 'Good'},
        prompt={"key": "value"},
    )

    agent_traits = Agent.example().traits
    agent_traits["agent_name"] = "Agent_0"

    try:
        assert result.sub_dicts["agent"] == agent_traits
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
        answer={'how_feeling': 'Good'},
        prompt={"key": "value"},
    )

    assert result.sub_dicts["agent"] == {
        "agent_name": "Arsenio Billingham",
        "show_status": "off the air",
    }


from edsl.results import Result
from edsl.agents import Agent
from edsl.scenarios import Scenario
from edsl.language_models import LanguageModel
from edsl import QuestionFreeText, Survey
from edsl.results import Results


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


def test_colliding_keys_keep_both_qualified_columns():
    survey = Survey([QuestionFreeText(question_name="q", question_text="Question?")])
    result = Result(
        agent=Agent.example(),
        scenario=Scenario({"sample_size": 37}),
        model=LanguageModel.example(),
        iteration=1,
        answer={"q": "answer"},
        survey=survey,
        randomization={"sample_size": 1},
    )
    results = Results(survey=survey, data=[result])

    assert "scenario.sample_size" in results.columns
    assert "randomization.sample_size" in results.columns
    selected = results.select("scenario.sample_size", "randomization.sample_size")
    assert selected.to_list() == [(37, 1)]

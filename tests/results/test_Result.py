
import pytest

from edsl.results import Result
from edsl.agents import Agent
from edsl.scenarios import Scenario
from edsl.language_models import LanguageModel
from edsl.results import Results
from edsl.surveys import Survey
from edsl import QuestionFreeText, Survey


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


def test_arbitrary_json_metadata_round_trip_and_selection(tmp_path):
    metadata = {
        "humanize_navigation": {
            "events": [
                {"event": "answer", "question": "q0", "revision": 1},
                {"event": "back", "from": "q1", "to": "q0"},
            ],
            "inactive_answers": {"q1": {"answer": "old", "revision": 1}},
        },
        "collection": {
            "started_at": "2026-08-05T14:30:00Z",
            "browser": {"name": "Firefox", "mobile": False},
        },
        "tags": ["human", None, 3],
        # Opaque metadata must not be revived as a FileStore merely because its
        # keys resemble one.
        "file_description": {"base64_string": "not-a-file", "path": "example"},
    }
    result = Result(
        agent=Agent.example(),
        scenario=Scenario.example(),
        model=LanguageModel.example(),
        iteration=1,
        answer={"q0": "yes"},
        metadata=metadata,
    )

    restored = Result.from_dict(result.to_dict())
    assert restored.metadata == metadata
    assert restored.sub_dicts["metadata"] == metadata

    results = Results(survey=Survey([]), data=[restored])
    assert Results.from_dict(results.to_dict()).first().metadata == metadata
    package_path = tmp_path / "metadata-results.ep"
    results.git.save(package_path)
    assert Results.git.load(package_path).first().metadata == metadata
    assert results.select("metadata.collection").to_list() == [
        {
            "started_at": "2026-08-05T14:30:00Z",
            "browser": {"name": "Firefox", "mobile": False},
        }
    ]


def test_metadata_survives_question_transformations():
    result = Result(
        agent=Agent.example(),
        scenario=Scenario.example(),
        model=LanguageModel.example(),
        iteration=1,
        answer={"q0": "yes", "q1": "no"},
        metadata={"source": {"kind": "human"}},
    )

    assert result.select("q0").data["metadata"] == result.data["metadata"]
    assert result.rename({"q0": "renamed"}).data["metadata"] == result.data["metadata"]
    assert result.by_question_data()["metadata_data"] == {
        "source": {"kind": "human"}
    }
    metadata_column = next(
        column["metadata_data"]
        for column in result.to_dataset().data
        if "metadata_data" in column
    )
    assert metadata_column == [
        {"source": {"kind": "human"}},
        {"source": {"kind": "human"}},
    ]


def test_metadata_rejects_non_json_values():
    with pytest.raises(TypeError, match="not JSON-compatible"):
        Result(
            agent=Agent.example(),
            scenario=Scenario.example(),
            model=LanguageModel.example(),
            iteration=1,
            answer={},
            metadata={"bad": {1, 2}},
        )


def test_metadata_collisions_preserve_qualified_columns():
    result = Result(
        agent=Agent.example(),
        scenario=Scenario({"source": "survey"}),
        model=LanguageModel.example(),
        iteration=1,
        answer={"source": "answer"},
        metadata={"source": "human"},
    )
    results = Results(survey=Survey([]), data=[result])

    assert "scenario.source" in results.columns
    assert "metadata.source" in results.columns
    assert results.select("scenario.source").to_list() == ["survey"]
    assert results.select("metadata.source").to_list() == ["human"]
    assert results.select("answer.source").to_list() == ["answer"]
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

import pytest
from edsl import Coop, Agent, Jobs, Model, Results, Survey
from edsl.questions import (
    QuestionMultipleChoice,
    QuestionLikertFive,
    QuestionYesNo,
    #    QuestionBudget,
)
from unittest.mock import patch, PropertyMock


@pytest.mark.coop
def test_coop_remote_inference_cost():
    coop = Coop(api_key="b")
    job = Jobs.example()
    cost = coop.remote_inference_cost(job)
    assert cost == 8
    survey = Survey(
        questions=[
            QuestionMultipleChoice.example(),
            QuestionLikertFive.example(),
            QuestionYesNo.example(),
            #       QuestionBudget.example(),
        ]
    )
    models = [Model("gpt-4o")]
    job = survey.by(models)
    cost = coop.remote_inference_cost(job)
    assert cost == 3
    survey = Survey(
        questions=[
            QuestionMultipleChoice.example(),
        ]
    )
    cost = coop.remote_inference_cost(survey)
    assert cost == 1
    with pytest.raises(TypeError):
        # Not valid input - we raise a TypeError from EDSL
        agent = Agent.example()
        coop.remote_inference_cost(agent)


@pytest.mark.coop
@patch(
    "edsl.Coop.edsl_settings",
    new_callable=PropertyMock,
    return_value={
        "remote_caching": False,
        "remote_inference": True,
        "remote_logging": False,
    },
)
def test_remote_inference_with_jobs(mock_edsl_settings):

    # Test a job with a description
    job = Jobs.example()
    result = job.run(remote_inference_description="Example of a completed job")
    assert isinstance(result, Results)
    # description = result.select("description").first()
    # status = result.select("status").first()
    # assert description == "Example of a completed job"
    # assert status == "queued"

    # Test a job with no description
    job = Jobs.example()
    result = job.run()
    assert isinstance(result, Results)
    # description = result.select("description").first()
    # status = result.select("status").first()
    # assert description == None
    # assert status == "queued"


@pytest.mark.coop
@patch(
    "edsl.Coop.edsl_settings",
    new_callable=PropertyMock,
    return_value={
        "remote_caching": False,
        "remote_inference": False,
        "remote_logging": False,
    },
)
def test_no_remote_inference_with_jobs(mock_edsl_settings):

    job = Jobs.example()
    results = job.run(
        remote_inference_description="This job will not be sent to the server"
    )
    assert isinstance(results, Results)
    assert results.question_names == ["how_feeling", "how_feeling_yesterday"]

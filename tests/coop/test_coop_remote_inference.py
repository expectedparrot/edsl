import pytest
from edsl import Coop, Jobs, Model, Survey, Results
from edsl.questions import (
    QuestionMultipleChoice,
    QuestionLikertFive,
    QuestionYesNo,
    QuestionBudget,
)
from unittest.mock import patch, PropertyMock


@pytest.mark.coop
def test_coop_remote_inference_cost():
    coop = Coop(api_key="b")
    job = Jobs.example()
    cost = coop.remote_inference_cost(job)
    assert cost == 16
    survey = Survey(
        questions=[
            QuestionMultipleChoice.example(),
            QuestionLikertFive.example(),
            QuestionYesNo.example(),
            QuestionBudget.example(),
        ]
    )
    job = Jobs(survey=survey, models=[Model("gpt-4o")])
    cost = coop.remote_inference_cost(job)
    assert cost == 8
    survey = Survey(
        questions=[
            QuestionMultipleChoice.example(),
        ]
    )
    job = Jobs(survey=survey, models=[Model("gpt-4o")])
    cost = coop.remote_inference_cost(job)
    assert cost == 2
    with pytest.raises(Exception):
        # Should be invalid JSON
        survey = Survey.example()
        coop.remote_inference_cost(survey)


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
    remote_job_data = job.run(remote_inference_description="Example of a completed job")
    assert type(remote_job_data) == dict
    assert remote_job_data.get("description") == "Example of a completed job"
    assert remote_job_data.get("status") == "queued"

    # Test a job with no description
    job = Jobs.example()
    remote_job_data = job.run()
    assert type(remote_job_data) == dict
    assert remote_job_data.get("description") == None
    assert remote_job_data.get("status") == "queued"


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

import pytest
from edsl import Coop, Jobs, Model, Survey
from edsl.questions import (
    QuestionMultipleChoice,
    QuestionLikertFive,
    QuestionYesNo,
    QuestionBudget,
)


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

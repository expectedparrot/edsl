import pytest

from edsl import (
    ProbabilisticResponse,
    QuestionLikertFive,
    QuestionLinearScale,
    QuestionYesNo,
)
from edsl.questions.question_base import QuestionBase


@pytest.mark.parametrize(
    ("question", "probabilities", "expected"),
    [
        (
            QuestionYesNo(
                question_name="attend",
                question_text="Will you attend?",
                probabilistic_response=ProbabilisticResponse(resolution="mode"),
            ),
            [0.2, 0.8],
            "Yes",
        ),
        (
            QuestionLinearScale(
                question_name="rating",
                question_text="How satisfied are you?",
                question_options=[1, 2, 3, 4, 5],
                option_labels={1: "Not at all", 5: "Extremely"},
                probabilistic_response=ProbabilisticResponse(resolution="mode"),
            ),
            [0.05, 0.1, 0.15, 0.6, 0.1],
            4,
        ),
        (
            QuestionLikertFive(
                question_name="agreement",
                question_text="I agree with this proposal.",
                probabilistic_response=ProbabilisticResponse(resolution="mode"),
            ),
            [0.05, 0.1, 0.15, 0.6, 0.1],
            "Agree",
        ),
    ],
)
def test_derived_questions_resolve_categorical_probabilities(
    question, probabilities, expected
):
    result = question._validate_answer({"answer": {"probabilities": probabilities}})
    assert result["answer"] == expected
    assert result["distribution"] == probabilities
    assert result["resolution_method"] == "mode"


@pytest.mark.parametrize(
    "question",
    [
        QuestionYesNo(
            question_name="attend",
            question_text="Will you attend?",
            probabilistic_response=ProbabilisticResponse(
                resolution="sample", seed=42
            ),
        ),
        QuestionLinearScale(
            question_name="rating",
            question_text="How satisfied are you?",
            question_options=[1, 2, 3, 4, 5],
            probabilistic_response=ProbabilisticResponse(
                resolution="sample", seed=42
            ),
        ),
        QuestionLikertFive(
            question_name="agreement",
            question_text="I agree with this proposal.",
            probabilistic_response=ProbabilisticResponse(
                resolution="sample", seed=42
            ),
        ),
    ],
)
def test_derived_questions_round_trip(question):
    restored = QuestionBase.from_dict(question.to_dict())
    assert restored.probabilistic_response == question.probabilistic_response


def test_derived_question_prompts_request_probability_vectors():
    yes_no = QuestionYesNo(
        question_name="attend",
        question_text="Will you attend?",
        probabilistic_response=ProbabilisticResponse(resolution="none"),
    )
    scale = QuestionLinearScale(
        question_name="rating",
        question_text="How satisfied are you?",
        question_options=[1, 2, 3],
        probabilistic_response=ProbabilisticResponse(resolution="none"),
    )
    likert = QuestionLikertFive(
        question_name="agreement",
        question_text="I agree with this proposal.",
        probabilistic_response=ProbabilisticResponse(resolution="none"),
    )
    assert '"probabilities" array' in yes_no.prompt_preview().text
    assert '"probabilities" array' in scale.prompt_preview().text
    assert '"probabilities" array' in likert.prompt_preview().text


def test_non_probabilistic_derived_questions_are_unchanged():
    assert (
        QuestionYesNo(
            question_name="attend", question_text="Will you attend?"
        )._validate_answer({"answer": "Yes"})["answer"]
        == "Yes"
    )
    assert (
        QuestionLinearScale(
            question_name="rating",
            question_text="How satisfied are you?",
            question_options=[1, 2, 3],
        )._validate_answer({"answer": 2})["answer"]
        == 2
    )
    assert (
        QuestionLikertFive(
            question_name="agreement",
            question_text="I agree with this proposal.",
        )._validate_answer({"answer": "Agree"})["answer"]
        == "Agree"
    )

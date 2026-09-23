"""Unselected options use runtime answers while preserving authoring references."""

import pytest

from edsl import QuestionCheckBox, QuestionMultipleChoice
from edsl.sharedstate.refs import AnswerRef


@pytest.mark.parametrize(
    "question_class,answer,remaining",
    [
        (QuestionMultipleChoice, "B", ["A", "C"]),
        (QuestionCheckBox, ["A", "C"], ["B"]),
        (QuestionCheckBox, [], ["A", "B", "C"]),
    ],
)
def test_unselected_distinguishes_unanswered_from_runtime_answers(
    question_class, answer, remaining
):
    question = question_class(
        question_name="q", question_text="Pick", question_options=["A", "B", "C"]
    )
    assert question.unselected == []
    assert question.answer == AnswerRef("q")

    question.answer = answer
    assert question.unselected == remaining
    assert question.answer == answer

    question.answer = None
    assert question.unselected == []

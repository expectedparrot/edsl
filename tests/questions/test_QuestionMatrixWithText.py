import pytest

from edsl.questions import QuestionBase, QuestionMatrixWithText
from edsl.questions.exceptions import (
    QuestionAnswerValidationError,
    QuestionCreationValidationError,
)


@pytest.fixture
def question():
    return QuestionMatrixWithText(
        question_name="service_quality",
        question_text="Rate the service dimensions.",
        question_items=["Speed", "Support"],
        question_options=[1, 2, 3],
        items_with_text=["Support"],
    )


def test_matrix_with_text_validates_selected_rows(question):
    question._validate_answer(
        {
            "answer": {
                "Speed": 2,
                "Support": {"choice": 3, "text": "Helpful and quick."},
            }
        }
    )
    question._validate_answer(
        {"answer": {"Speed": 2, "Support": {"choice": 3}}}
    )


def test_matrix_with_text_rejects_invalid_choice(question):
    with pytest.raises(QuestionAnswerValidationError):
        question._validate_answer(
            {"answer": {"Speed": 2, "Support": {"choice": 4, "text": "No"}}}
        )


def test_matrix_with_text_rejects_object_for_plain_row(question):
    with pytest.raises(QuestionAnswerValidationError):
        question._validate_answer(
            {"answer": {"Speed": {"choice": 2}, "Support": {"choice": 3}}}
        )


def test_matrix_with_text_round_trip(question):
    restored = QuestionBase.from_dict(question.to_dict())

    assert isinstance(restored, QuestionMatrixWithText)
    assert restored.items_with_text == ["Support"]
    restored._validate_answer(
        {"answer": {"Speed": 1, "Support": {"choice": 2, "text": None}}}
    )


def test_matrix_with_text_rejects_unknown_rows():
    with pytest.raises(QuestionCreationValidationError, match="question_items"):
        QuestionMatrixWithText(
            question_name="service_quality",
            question_text="Rate the service dimensions.",
            question_items=["Speed"],
            question_options=[1, 2, 3],
            items_with_text=["Support"],
        )


def test_matrix_with_text_html_has_text_input_only_for_configured_rows(question):
    html = question.question_html_content

    assert 'name="service_quality_Support_text"' in html
    assert 'name="service_quality_Speed_text"' not in html

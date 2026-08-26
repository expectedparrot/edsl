"""Tests for checkbox questions that accept custom responses."""

import pytest

from edsl.questions import QuestionBase, QuestionCheckBoxWithOther
from edsl.questions.exceptions import QuestionAnswerValidationError


@pytest.fixture
def question():
    return QuestionCheckBoxWithOther(
        question_name="foods",
        question_text="Which foods do you enjoy?",
        question_options=["Pizza", "Pasta", "Salad"],
        min_selections=1,
        max_selections=3,
    )


def test_construction(question):
    assert question.question_type == "checkbox_with_other"
    assert question.question_options == ["Pizza", "Pasta", "Salad"]
    assert question.other_option_text == "Other"
    assert question.min_selections == 1
    assert question.max_selections == 3


def test_accepts_predefined_and_multiple_custom_responses(question):
    response = {
        "answer": ["Pizza", "Other: Sushi", "Other: Curry"],
        "comment": "These are my favorites.",
    }

    validated = question.response_validator.validate(response)

    assert validated["answer"] == ["Pizza", "Other: Sushi", "Other: Curry"]
    assert validated["comment"] == "These are my favorites."


def test_accepts_multiple_custom_responses_case_insensitively(question):
    response = {"answer": ["Other: Sushi", "other: Curry"]}

    validated = question.response_validator.validate(response)

    assert validated["answer"] == ["Other: Sushi", "other: Curry"]


@pytest.mark.parametrize(
    "answer",
    [
        ["Unknown"],
        ["Pizza", "Other:"],
        ["Pizza", "Something else: Sushi"],
    ],
)
def test_rejects_invalid_custom_responses(question, answer):
    with pytest.raises(QuestionAnswerValidationError):
        question.response_validator.validate({"answer": answer})


def test_enforces_selection_limits(question):
    with pytest.raises(QuestionAnswerValidationError, match="at least 1"):
        question.response_validator.validate({"answer": []})

    with pytest.raises(QuestionAnswerValidationError, match="at most 3"):
        question.response_validator.validate(
            {
                "answer": [
                    "Pizza",
                    "Other: Sushi",
                    "Other: Curry",
                    "Other: Tacos",
                ]
            }
        )


def test_custom_other_option_text():
    question = QuestionCheckBoxWithOther(
        question_name="foods",
        question_text="Which foods do you enjoy?",
        question_options=["Pizza", "Pasta"],
        other_option_text="Something else",
    )

    validated = question.response_validator.validate(
        {"answer": ["Pizza", "something else: Sushi"]}
    )

    assert validated["answer"] == ["Pizza", "something else: Sushi"]

    with pytest.raises(QuestionAnswerValidationError):
        question.response_validator.validate({"answer": ["Other: Sushi"]})


def test_use_code_applies_only_to_predefined_options():
    question = QuestionCheckBoxWithOther(
        question_name="foods",
        question_text="Which foods do you enjoy?",
        question_options=["Pizza", "Pasta", "Salad"],
        use_code=True,
    )

    validated = question.response_validator.validate({"answer": [0, 2, "Other: Sushi"]})

    assert validated["answer"] == [0, 2, "Other: Sushi"]

    with pytest.raises(QuestionAnswerValidationError):
        question.response_validator.validate({"answer": ["Pizza"]})


def test_serialization_round_trip(question):
    serialized = question.to_dict()

    assert serialized["question_type"] == "checkbox_with_other"
    assert serialized["other_option_text"] == "Other"

    restored = QuestionBase.from_dict(serialized)

    assert isinstance(restored, QuestionCheckBoxWithOther)
    assert restored == question


def test_exclusive_option_is_alone_and_exempt_from_selection_minimum():
    question = QuestionCheckBoxWithOther(
        question_name="foods",
        question_text="Which foods do you enjoy?",
        question_options=["Pizza", "Pasta", "None"],
        min_selections=2,
        exclusive_options=["None"],
    )

    assert question._validate_answer({"answer": ["None"]})["answer"] == ["None"]
    with pytest.raises(QuestionAnswerValidationError, match="selected by themselves"):
        question._validate_answer({"answer": ["Pizza", "None"]})
    with pytest.raises(QuestionAnswerValidationError, match="selected by themselves"):
        question._validate_answer({"answer": ["None", "Other: Sushi"]})

    restored = QuestionBase.from_dict(question.to_dict())
    assert restored.exclusive_options == ["None"]


def test_exclusive_option_with_codes():
    question = QuestionCheckBoxWithOther(
        question_name="foods",
        question_text="Which foods do you enjoy?",
        question_options=["Pizza", "Pasta", "None"],
        use_code=True,
        exclusive_options=["None"],
    )

    assert question._validate_answer({"answer": [2]})["answer"] == [2]
    with pytest.raises(QuestionAnswerValidationError, match="selected by themselves"):
        question._validate_answer({"answer": [2, "Other: Sushi"]})


def test_prompt_and_html_include_other_option(question):
    replacements = question.data
    presentation = question.question_presentation.render(replacements)
    instructions = question.answering_instructions.render(replacements)

    assert "Other: [your custom response]" in presentation
    assert '"Other: another choice"' in instructions

    html = question.question_html_content
    assert 'value="Other"' in html
    assert 'name="foods_other_text"' in html

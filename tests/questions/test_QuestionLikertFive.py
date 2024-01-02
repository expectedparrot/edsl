import pytest
from edsl.questions import QuestionLikertFive
from edsl.questions.derived.QuestionLikertFive import QuestionLikertFiveEnhanced
from edsl.questions import Question

valid_question = {
    "question_text": "You like pizza. How strongly do you dis/agree?",
    "short_names_dict": {},
}

valid_question_w_extras = {
    "question_text": "On a scale from 1 to 5, how much do you like pizza?",
    "question_options": ["Bleh", "Eeeh", "M", "Mmmm", "Mmmmmm"],
    "question_name": "pizza_love",
    "short_names_dict": {},
}

default_options = [
    "Strongly disagree",
    "Disagree",
    "Neutral",
    "Agree",
    "Strongly agree",
]


def test_QuestionLikertFive_construction():
    """Test QuestionLikertFive construction."""

    # QuestionLikertFive should impute extra fields appropriately
    q = QuestionLikertFive(**valid_question)
    assert isinstance(q, QuestionLikertFiveEnhanced)
    assert q.question_text == valid_question["question_text"]
    assert q.question_name == None
    assert q.question_options == default_options
    assert q.uuid is not None
    assert q.answer_data_model is not None
    assert q.data != valid_question
    # should raise an exception if unexpected attribute is present
    invalid_question = valid_question.copy()
    invalid_question.update({"unexpected_attribute": "unexpected_attribute"})
    with pytest.raises(Exception):
        QuestionLikertFive(**invalid_question)

    # QuestionLikertFive construction with all fields
    q = QuestionLikertFive(**valid_question_w_extras)
    assert q.question_name == valid_question_w_extras["question_name"]
    assert q.question_text == valid_question_w_extras["question_text"]
    assert q.question_options == valid_question_w_extras["question_options"]
    assert q.uuid is not None
    assert q.answer_data_model is not None
    assert q.data == valid_question_w_extras


def test_QuestionLikertFive_serialization():
    """Test QuestionLikertFive serialization."""

    # serialization should add a "type" attribute
    q = QuestionLikertFive(**valid_question)
    assert q.to_dict() == {
        "question_text": valid_question["question_text"],
        "question_options": default_options,
        "question_name": None,
        "type": "likert_five",
        "short_names_dict": {},
    }

    # deserialization should return a QuestionLikertFiveEnhanced object
    q_lazarus = Question.from_dict(q.to_dict())
    assert isinstance(q_lazarus, QuestionLikertFiveEnhanced)
    assert type(q) == type(q_lazarus)
    # but if no question_name is provided, then a new one should be generated
    assert repr(q) != repr(q_lazarus)

    q_extras = QuestionLikertFive(**valid_question_w_extras)
    q_lazarus = Question.from_dict(q_extras.to_dict())
    assert repr(q_extras) == repr(q_lazarus)


def test_QuestionLikertFive_extras():
    """Test QuestionFreeText extra functionalities."""
    q = QuestionLikertFive(**valid_question)
    # instructions
    assert "You are being asked" in q.instructions
    assert "{{question_text}}" in q.instructions
    assert "for option in question_options" in q.instructions
    # form elements
    assert f"{q.question_text}" in q.form_elements()

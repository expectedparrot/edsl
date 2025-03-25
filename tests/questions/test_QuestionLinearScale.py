import pytest
from edsl.questions.exceptions import (
    QuestionAnswerValidationError,
    QuestionCreationValidationError,
)
from edsl.questions import QuestionBase, QuestionLinearScale


def test_QuestionLinearScale_main():
    # Commented out as main is no longer directly imported
    # main()
    pass


valid_question = {
    "question_text": "On a scale from 1 to 5, how much do you like pizza?",
    "question_options": [1, 2, 3, 4, 5],
    "question_name": "pizza",
}

valid_question_w_extras = {
    "question_text": "On a scale from 1 to 5, how much do you like pizza?",
    "question_options": [1, 2, 3, 4, 5],
    "option_labels": {1: "Bleh", 2: "Eeh", 3: "OK", 4: "Mm", 5: "Mmmm"},
    "question_name": "pizza",
}


def test_QuestionLinearScale_construction():
    """Test QuestionLinearScale construction."""

    q = QuestionLinearScale(**valid_question)
    assert isinstance(q, QuestionLinearScale)
    assert q.question_name == valid_question["question_name"]
    assert q.question_text == valid_question["question_text"]
    assert q.question_options == valid_question["question_options"]
    assert q.option_labels == {}

    assert q.data != valid_question

    # should raise an exception if option_labels is not None and not a dict
    invalid_question = valid_question.copy()
    invalid_question.update({"option_labels": "option_labels"})
    with pytest.raises(Exception):
        QuestionLinearScale(**invalid_question)
    # or if option_labels is a dict but not of type int -> str
    invalid_question.update({"option_labels": {1: 1}})
    with pytest.raises(Exception):
        QuestionLinearScale(**invalid_question)
    # or if it doesn't have the same keys as question_options
    invalid_question.update({"option_labels": {1: "OK", 3: "OK"}})
    with pytest.raises(Exception):
        QuestionLinearScale(**invalid_question)
    # or if it doesn't have a label for the last option
    invalid_question.update({"option_labels": {1: "OK"}})
    with pytest.raises(Exception):
        QuestionLinearScale(**invalid_question)
    # or if it doesn't have a label for the first option
    invalid_question.update({"option_labels": {5: "OK"}})
    with pytest.raises(Exception):
        QuestionLinearScale(**invalid_question)
    # or if it has a key that is not in question_options
    invalid_question.update({"option_labels": {1: "OK", 5: "OK", 1.5: "OK"}})
    with pytest.raises(Exception):
        QuestionLinearScale(**invalid_question)
    # but first and last only are valid
    invalid_question.update({"option_labels": {1: "OK", 5: "OK"}})
    with pytest.raises(Exception):
        QuestionLinearScale(**invalid_question)
    # should raise an exception if unexpected attribute is present
    invalid_question = valid_question.copy()
    invalid_question.update({"unexpected_attribute": "unexpected_attribute"})
    with pytest.raises(Exception):
        QuestionLinearScale(**invalid_question)

    # QuestionLinearScale should impute extra fields appropriately
    q = QuestionLinearScale(**valid_question_w_extras)
    assert q.question_name == valid_question["question_name"]
    assert q.question_text == valid_question["question_text"]
    assert q.question_options == valid_question["question_options"]
    assert q.option_labels == valid_question_w_extras["option_labels"]

    assert q.data == valid_question_w_extras


def test_QuestionLinearScale_serialization():
    """Test QuestionLinearScale serialization."""

    # serialization should add a "type" attribute
    q = QuestionLinearScale(**valid_question)
    print(q.to_dict())

    assert {
        "question_text": "On a scale from 1 to 5, how much do you like pizza?",
        "question_options": [1, 2, 3, 4, 5],
        "question_name": "pizza",
        "option_labels": {},
        "question_type": "linear_scale",
    }.items() <= q.to_dict().items()

    # deserialization should return a QuestionLinearScaleEnhanced object
    q_lazarus = QuestionBase.from_dict(q.to_dict())
    assert isinstance(q_lazarus, QuestionLinearScale)
    assert type(q) == type(q_lazarus)
    assert repr(q) == repr(q_lazarus)

    # serialization from bad data should raise an exception
    with pytest.raises(QuestionCreationValidationError):
        QuestionLinearScale.from_dict(
            {
                "question_text": "On a scale from 1 to 5, how much do you like pizza?",
                "question_options": [1, -2, 3, 4, 5],
                "question_name": "pizza",
                "option_labels": {},
                "question_type": "linear_scale",
            }
        )
    with pytest.raises(QuestionCreationValidationError):
        QuestionBase.from_dict(
            {
                "question_text": "On a scale from 1 to 5, how much do you like pizza?",
                "question_options": [1, 2, 3, 4, 5],
                "question_name": "pizza",
                "option_labels": {1: 1, 5: [1, 1]},
                "question_type": "linear_scale",
            }
        )


def test_QuestionLinearScale_answers():
    q = QuestionLinearScale(**valid_question)

    # answer must be an integer or interpretable as integer
    q._validate_answer({"answer": 1})
    # TODO: should the following three be allowed?
    # q._validate_answer({"answer": "1"})
    # q._validate_answer({"answer": True})
    q._validate_answer({"answer": 1, "comment": "I'm good"})
    # answer value required
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": None})
    # answer must be in range of question_options
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": 6})
    # answer can't be a random string
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": "asdf"})
    # with pytest.raises(QuestionAnswerValidationError):
    #     q._validate_answer({"answer": [0, 1]})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": {"answer": 0}})


def test_QuestionLinearScale_extras():
    """Test QuestionFreeText extra functionalities."""
    q = QuestionLinearScale(**valid_question)
    # instructions
    # _simulate_answer
    assert q._simulate_answer().keys() == q._simulate_answer(human_readable=True).keys()
    assert q._simulate_answer(human_readable=False)["answer"] in q.question_options
    simulated_answer = q._simulate_answer()
    assert isinstance(simulated_answer, dict)
    assert "answer" in simulated_answer
    assert "comment" in simulated_answer
    # assert isinstance(simulated_answer["answer"], int)
    assert simulated_answer["answer"] in q.question_options
    # form elements

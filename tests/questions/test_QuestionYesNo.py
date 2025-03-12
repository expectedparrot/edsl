import pytest
from edsl.questions.exceptions import (
    QuestionResponseValidationError,
    QuestionAnswerValidationError,
)
from edsl.questions import QuestionBase
from edsl.questions.derived.question_yes_no import QuestionYesNo, main


def test_QuestionYesNo_main():
    # main()
    pass


valid_question = {
    "question_text": "Do you like pizza?",
    "question_options": ["Yes", "No"],
    "question_name": "pizza",
}


def test_QuestionYesNo_construction():
    """Test QuestionYesNo construction."""

    q = QuestionYesNo(**valid_question)
    assert isinstance(q, QuestionYesNo)
    assert q.question_name == valid_question["question_name"]
    assert q.question_text == valid_question["question_text"]
    assert q.question_options == valid_question["question_options"]

    assert q.data == valid_question

    no_yes = valid_question.copy()
    no_yes.update({"question_options": ["No", "Yes"]})
    q = QuestionYesNo(**no_yes)

    # should raise an exception if question_options is a list
    invalid_question = valid_question.copy()
    invalid_question.update({"question_options": "question_options"})
    with pytest.raises(Exception):
        QuestionYesNo(**invalid_question)
    # or not exactly == ["Yes", "No"]
    invalid_question.update({"question_options": ["Yes", "No", "Maybe"]})
    with pytest.raises(Exception):
        QuestionYesNo(**invalid_question)


def test_QuestionYesNo_serialization():
    """Test QuestionYesNo serialization."""

    # serialization should add a "type" attribute
    q = QuestionYesNo(**valid_question)
    print(q.to_dict())
    assert {
        "question_name": valid_question["question_name"],
        "question_text": valid_question["question_text"],
        "question_options": ["Yes", "No"],
        "question_type": "yes_no",
    }.items() <= q.to_dict().items()

    # deserialization should return a QuestionYesNoEnhanced object
    q_lazarus = QuestionBase.from_dict(q.to_dict())
    assert isinstance(q_lazarus, QuestionYesNo)
    assert type(q) == type(q_lazarus)
    assert repr(q) == repr(q_lazarus)


def test_QuestionYesNo_answers():
    q = QuestionYesNo(**valid_question)
    llm_response_valid1 = {"answer": "Yes", "comment": "I'm good"}
    llm_response_valid2 = {"answer": "No"}
    llm_response_invalid1 = {"comment": "I'm good"}

    # LLM response is required to have an answer key, but is flexible otherwise
    # q._validate_response(llm_response_valid1)
    # q._validate_response(llm_response_valid2)
    # with pytest.raises(QuestionResponseValidationError):
    #     q._validate_response(llm_response_invalid1)

    # answer must be an integer or interpretable as integer
    q._validate_answer({"answer": "Yes"})
    # TODO: should the following three be allowed?
    q._validate_answer({"answer": "No"})
    q._validate_answer({"answer": "Yes"})
    q._validate_answer({"answer": "No", "comment": "I'm good"})
    # answer value required
    #    with pytest.raises(QuestionAnswerValidationError):
    #        q._validate_answer({"answer": None})
    # answer must be in range of question_options
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": "2"})
    # answer can't be a random string
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": "asdf"})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": [0, 1]})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": {"answer": 0}})

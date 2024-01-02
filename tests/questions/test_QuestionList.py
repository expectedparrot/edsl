import pytest
import uuid
from edsl.exceptions import (
    QuestionAnswerValidationError,
    QuestionResponseValidationError,
)
from edsl.questions import Question, QuestionList, Settings
from edsl.questions.QuestionList import QuestionListEnhanced

valid_question = {
    "question_text": "How do you change a car tire?",
    "question_name": "tire_change",
    "allow_nonresponse": False,
    "max_list_items": None,
    "short_names_dict": {},
}

valid_question_wo_extras = {
    "question_text": "How do you change a car tire?",
    "question_name": "tire_change",
    "short_names_dict": {},
}

valid_question_w_extras = {
    "question_text": "How do you change a car tire?",
    "question_name": "tire_change",
    "allow_nonresponse": True,
    "max_list_items": 5,
    "short_names_dict": {},
}


def test_QuestionList_construction():
    """Test QuestionList construction."""

    q = QuestionList(**valid_question)
    assert isinstance(q, QuestionListEnhanced)
    assert q.question_name == valid_question["question_name"]
    assert q.question_text == valid_question["question_text"]
    assert q.allow_nonresponse == valid_question["allow_nonresponse"]
    assert q.uuid is not None
    assert q.answer_data_model is not None
    assert q.data == valid_question

    # QuestionList should impute extra fields appropriately
    q = QuestionList(**valid_question_wo_extras)
    assert q.question_name == valid_question_wo_extras["question_name"]
    assert q.question_text == valid_question_wo_extras["question_text"]
    assert q.allow_nonresponse == False
    assert q.max_list_items == None
    assert q.uuid is not None
    assert q.answer_data_model is not None
    assert q.data != valid_question_wo_extras
    assert q.data == valid_question

    # should raise an exception if question_text is missing
    invalid_question = valid_question.copy()
    invalid_question.pop("question_text")
    with pytest.raises(Exception):
        QuestionList(**invalid_question)
    # should raise an exception if question_text is empty
    invalid_question = valid_question.copy()
    invalid_question.update({"question_text": ""})
    with pytest.raises(Exception):
        QuestionList(**invalid_question)
    # should raise an exception if question_text is too long
    invalid_question = valid_question.copy()
    invalid_question.update({"question_text": "a" * (Settings.MAX_QUESTION_LENGTH + 1)})
    with pytest.raises(Exception):
        QuestionList(**invalid_question)
    # should raise an exception if unexpected attribute is present
    invalid_question = valid_question.copy()
    invalid_question.update({"unexpected_attribute": "unexpected_attribute"})
    with pytest.raises(Exception):
        QuestionList(**invalid_question)


def test_QuestionList_serialization():
    """Test QuestionList serialization."""

    # serialization should add a "type" attribute
    q = QuestionList(**valid_question)
    valid_question_w_type = valid_question.copy()
    valid_question_w_type.update({"type": "list"})
    assert q.to_dict() == valid_question_w_type
    q = QuestionList(**valid_question_w_extras)
    valid_question_w_type = valid_question_w_extras.copy()
    valid_question_w_type.update({"type": "list"})
    assert q.to_dict() == valid_question_w_type
    # and optional attributes if not present
    q = QuestionList(**valid_question_wo_extras)
    valid_question_w_type = valid_question_wo_extras.copy()
    valid_question_w_type.update(
        {"type": "list", "allow_nonresponse": False, "max_list_items": None}
    )
    assert q.to_dict() == valid_question_w_type

    # deserialization should return a QuestionListEnhanced object
    q_lazarus = Question.from_dict(q.to_dict())
    assert isinstance(q_lazarus, QuestionListEnhanced)
    assert type(q) == type(q_lazarus)
    assert repr(q) == repr(q_lazarus)

    # serialization from bad data should raise an exception
    with pytest.raises(Exception):
        Question.from_dict({"type": "list"})
    with pytest.raises(Exception):
        Question.from_dict({"type": "list", "question_text": 1})
    with pytest.raises(Exception):
        Question.from_dict({"type": "list", "question_text": ""})
    with pytest.raises(Exception):
        Question.from_dict(
            {"type": "list", "question_text": "", "allow_nonresponse": "yes"}
        )
    with pytest.raises(Exception):
        Question.from_dict(
            {
                "type": "list",
                "question_text": "",
                "max_list_items": "yes",
                "short_names_dict": {},
            }
        )
    with pytest.raises(Exception):
        Question.from_dict(
            {
                "type": "list",
                "question_text": "How do you change a tire?",
                "tires": 4,
                "short_names_dict": {},
            }
        )


def test_QuestionList_answers():
    q = QuestionList(**valid_question)
    q_empty = QuestionList(**valid_question_w_extras)
    response_good = {
        "answer": ["First take off old tire.", "Next put on a new tire."],
        "comment": "You got this!",
    }
    response_bad = {
        "answer": ["First take off old tire.", "Next put on a new tire."],
        "comment": "OK",
        "extra": "extra",
    }
    response_terrible = {"you": "will never be able to do this!"}

    # LLM responses are only required to have an "answer" key
    q.validate_response(response_good)
    with pytest.raises(QuestionResponseValidationError):
        q.validate_response(response_terrible)
    # but can have additional keys
    q.validate_response(response_bad)

    # answer validation
    q.validate_answer(response_good)
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer(response_terrible)
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer({"answer": 1})

    # missing answer cases
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer({"answer": []})
    q_empty.validate_answer({"answer": []})

    # too many answers
    with pytest.raises(QuestionAnswerValidationError):
        q_empty.validate_answer(
            {"answer": [str(uuid.uuid4()) for _ in range(q_empty.max_list_items + 1)]}
        )

    # code -> answer translation
    assert q.translate_answer_code_to_answer(response_good, None) == response_good


def test_test_QuestionList_extras():
    """Test QuestionList extra functionalities."""
    q = QuestionList(**valid_question)
    # instructions
    assert "Your response" in q.instructions
    # simulate_answer
    simulated_answer = q.simulate_answer()
    assert isinstance(simulated_answer, dict)
    assert "answer" in simulated_answer
    assert isinstance(simulated_answer["answer"], list)
    # form elements
    assert 'label for="tire_change"' in q.form_elements()

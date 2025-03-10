import pytest
import uuid
from edsl.questions.exceptions import (
    QuestionAnswerValidationError,
    QuestionResponseValidationError,
)
from edsl.questions import Settings
from edsl.questions import QuestionBase
from edsl.questions.question_list import QuestionList, main
from edsl.language_models import LanguageModel


def test_QuestionList_main():
    main()


valid_question = {
    "question_text": "How do you change a car tire?",
    "question_name": "tire_change",
    "max_list_items": None,
}

valid_question_wo_extras = {
    "question_text": "How do you change a car tire?",
    "question_name": "tire_change",
}

valid_question_w_extras = {
    "question_text": "How do you change a car tire?",
    "question_name": "tire_change",
    "max_list_items": 5,
}


def test_QuestionList_construction():
    """Test QuestionList construction."""

    q = QuestionList(**valid_question)
    assert isinstance(q, QuestionList)
    assert q.question_name == valid_question["question_name"]
    assert q.question_text == valid_question["question_text"]

    assert q.data == valid_question

    # QuestionList should impute extra fields appropriately
    q = QuestionList(**valid_question_wo_extras)
    assert q.question_name == valid_question_wo_extras["question_name"]
    assert q.question_text == valid_question_wo_extras["question_text"]
    assert q.max_list_items == None

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
    # invalid_question = valid_question.copy()
    # invalid_question.update({"question_text": "a" * (Settings.MAX_QUESTION_LENGTH + 1)})
    # with pytest.raises(Exception):
    #     QuestionList(**invalid_question)
    # should raise an exception if unexpected attribute is present
    invalid_question = valid_question.copy()
    invalid_question.update({"unexpected_attribute": "unexpected_attribute"})
    with pytest.raises(Exception):
        QuestionList(**invalid_question)


def remove_none_values(d):
    return {k: v for k, v in d.items() if v is not None}


def test_QuestionList_serialization():
    """Test QuestionList serialization."""

    # serialization should add a "type" attribute
    q = QuestionList(**valid_question)
    valid_question_w_type = valid_question.copy()
    valid_question_w_type.update({"question_type": "list"})
    assert remove_none_values(valid_question_w_type).items() <= q.to_dict().items()

    q = QuestionList(**valid_question_w_extras)
    valid_question_w_type = valid_question_w_extras.copy()
    valid_question_w_type.update({"question_type": "list"})
    assert valid_question_w_type.items() <= q.to_dict().items()
    # and optional attributes if not present

    q = QuestionList(**valid_question_wo_extras)
    valid_question_w_type = valid_question_wo_extras.copy()
    valid_question_w_type.update({"question_type": "list", "max_list_items": None})
    assert remove_none_values(valid_question_w_type).items() <= q.to_dict().items()

    # deserialization should return a QuestionListEnhanced object
    q_lazarus = QuestionBase.from_dict(q.to_dict())
    assert isinstance(q_lazarus, QuestionList)
    assert type(q) == type(q_lazarus)
    assert repr(q) == repr(q_lazarus)

    # serialization from bad data should raise an exception
    with pytest.raises(Exception):
        QuestionBase.from_dict({"type": "list"})
    with pytest.raises(Exception):
        QuestionBase.from_dict({"type": "list", "question_text": 1})
    with pytest.raises(Exception):
        QuestionBase.from_dict({"type": "list", "question_text": ""})
    with pytest.raises(Exception):
        QuestionBase.from_dict({"type": "list", "question_text": ""})
    with pytest.raises(Exception):
        QuestionBase.from_dict(
            {
                "type": "list",
                "question_text": "",
                "max_list_items": "yes",
            }
        )
    with pytest.raises(Exception):
        QuestionBase.from_dict(
            {
                "type": "list",
                "question_text": "How do you change a tire?",
                "tires": 4,
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
    # q._validate_response(response_good)
    # with pytest.raises(QuestionResponseValidationError):
    #     q._validate_response(response_terrible)
    # # but can have additional keys
    # q._validate_response(response_bad)

    # answer validation
    q._validate_answer(response_good)
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer(response_terrible)
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": 1})

    # missing answer cases
    #    with pytest.raises(QuestionAnswerValidationError):
    #        q._validate_answer({"answer": []})
    q_empty._validate_answer({"answer": []})

    # too many answers
    with pytest.raises(QuestionAnswerValidationError):
        q_empty._validate_answer(
            {"answer": [str(uuid.uuid4()) for _ in range(q_empty.max_list_items + 1)]}
        )

    # code -> answer translation
    assert q._translate_answer_code_to_answer(response_good, None) == response_good


def test_test_QuestionList_extras():
    """Test QuestionList extra functionalities."""
    q = QuestionList(**valid_question)
    # instructions
    # _simulate_answer
    simulated_answer = q._simulate_answer()
    assert isinstance(simulated_answer, dict)
    assert "answer" in simulated_answer
    assert isinstance(simulated_answer["answer"], list)
    # form elements


def test_repairs():
    q = QuestionList(question_text="Blah", question_name="list_of_foods")
    from edsl.language_models import LanguageModel

    m = LanguageModel.example(
        test_model=True, canned_response="""["{'a':1}", "{'b':2}"]"""
    )
    results = q.by(m).run()
    results.select("answer.list_of_foods").print()
    assert results.select("answer.list_of_foods").to_list()[0][0]["a"] == 1
    assert results.select("answer.list_of_foods").to_list()[0][1]["b"] == 2

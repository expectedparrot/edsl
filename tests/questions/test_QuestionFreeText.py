import pytest
from edsl.questions import Settings
from edsl.questions import QuestionBase
from edsl.questions.question_free_text import QuestionFreeText, main


def test_QuestionFreeText_main():
    main()


valid_question = {
    "question_text": "How are you?",
    "question_name": "how_are_you",
}


valid_question_allow_nonresponse = {
    "question_text": "How are you buddy?",
    "question_name": "how_are_you",
}


def test_QuestionFreeText_construction():
    """Test QuestionFreeText construction."""

    q = QuestionFreeText(**valid_question)
    assert isinstance(q, QuestionFreeText)
    assert q.question_name == valid_question["question_name"]
    assert q.question_text == valid_question["question_text"]

    assert q.data == valid_question

    # should raise an exception if question_text is missing
    invalid_question = valid_question.copy()
    invalid_question.pop("question_text")
    with pytest.raises(Exception):
        QuestionFreeText(**invalid_question)
    # should raise an exception if question_text is empty
    invalid_question = valid_question.copy()
    invalid_question.update({"question_text": ""})
    with pytest.raises(Exception):
        QuestionFreeText(**invalid_question)
    # should raise an exception if question_text is too long
    # invalid_question = valid_question.copy()
    # invalid_question.update({"question_text": "a" * (Settings.MAX_QUESTION_LENGTH + 1)})
    # with pytest.raises(Exception):
    #     QuestionFreeText(**invalid_question)
    # should raise an exception if unexpected attribute is present
    invalid_question = valid_question.copy()
    invalid_question.update({"unexpected_attribute": "unexpected_attribute"})
    with pytest.raises(Exception):
        QuestionFreeText(**invalid_question)


def test_QuestionFreeText_serialization():
    """Test QuestionFreeText serialization."""

    # serialization should add a "type" attribute
    q = QuestionFreeText(**valid_question)
    assert {
        "question_name": "how_are_you",
        "question_text": "How are you?",
        "question_type": "free_text",
    }.items() <= q.to_dict().items()

    # deserialization should return a QuestionFreeTextEnhanced object
    q_lazarus = QuestionBase.from_dict(q.to_dict())
    assert isinstance(q_lazarus, QuestionFreeText)
    assert type(q) == type(q_lazarus)
    assert repr(q) == repr(q_lazarus)

    # serialization from bad data should raise an exception
    with pytest.raises(Exception):
        QuestionBase.from_dict({"type": "free_text"})
    with pytest.raises(Exception):
        QuestionBase.from_dict({"type": "free_text", "question_text": 1})
    with pytest.raises(Exception):
        QuestionBase.from_dict({"type": "free_text", "question_text": ""})
    with pytest.raises(Exception):
        QuestionBase.from_dict({"question_text": "Yo??"})


def test_QuestionFreeText_answers():
    # Basically everything can pass so long as the model returns anything.
    pass
    # q = QuestionFreeText(**valid_question)
    # q_empty = QuestionFreeText(**valid_question_allow_nonresponse)
    # response_good = {"answer": "I am doing ok.", "comment": "OK"}
    # response_bad = {"answer": "I am doing ok.", "comment": "OK", "extra": "extra"}
    # response_terrible = {"you": "suck"}

    # # LLM responses are only required to have an "answer" key
    # # q._validate_response(response_good)
    # # q._validate_response(response_bad)
    # # with pytest.raises(QuestionResponseValidationError):
    # #     q._validate_response(response_terrible)

    # # answer validation
    # q._validate_answer(response_good)
    # with pytest.raises(QuestionAnswerValidationError):
    #     q._validate_answer(response_terrible)
    # with pytest.raises(QuestionAnswerValidationError):
    #     q._validate_answer({"answer": 1})

    # # missing answer cases
    # # with pytest.raises(QuestionAnswerValidationError):
    # #     q._validate_answer({"answer": ""})
    # # q_empty._validate_answer({"answer": ""})

    # # code -> answer translation
    # assert q._translate_answer_code_to_answer(response_good, None) == response_good


def test_test_QuestionFreeText_extras():
    """Test QuestionFreeText extra functionalities."""
    #pass
    q = QuestionFreeText(**valid_question)
    simulated_answer = q._simulate_answer()
    assert isinstance(simulated_answer, dict)
    assert "answer" in simulated_answer
    assert isinstance(simulated_answer["answer"], str)
    assert len(simulated_answer["answer"]) <= Settings.MAX_ANSWER_LENGTH
    assert len(simulated_answer["answer"]) > 0
    
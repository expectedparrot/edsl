import pytest
from edsl.exceptions import QuestionAnswerValidationError
from edsl.questions import Question, Settings
from edsl.questions.QuestionFreeText import QuestionFreeText, main


def test_QuestionFreeText_main():
    main()


valid_question = {
    "question_text": "How are you?",
    "allow_nonresponse": False,
    "question_name": "how_are_you",
}

valid_question_wo_nonresponse = {
    "question_text": "How are you buddy?",
    "question_name": "how_are_you",
}

valid_question_allow_nonresponse = {
    "question_text": "How are you buddy?",
    "allow_nonresponse": True,
    "question_name": "how_are_you",
}


def test_QuestionFreeText_construction():
    """Test QuestionFreeText construction."""

    q = QuestionFreeText(**valid_question)
    assert isinstance(q, QuestionFreeText)
    assert q.question_name == valid_question["question_name"]
    assert q.question_text == valid_question["question_text"]
    assert q.allow_nonresponse == valid_question["allow_nonresponse"]

    assert q.data == valid_question

    # QuestionFreeText should impute allow_nonresponse with False
    q = QuestionFreeText(**valid_question_wo_nonresponse)
    assert q.question_name == valid_question_wo_nonresponse["question_name"]
    assert q.question_text == valid_question_wo_nonresponse["question_text"]
    assert q.allow_nonresponse == False

    assert q.data != valid_question_wo_nonresponse

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
    invalid_question = valid_question.copy()
    invalid_question.update({"question_text": "a" * (Settings.MAX_QUESTION_LENGTH + 1)})
    with pytest.raises(Exception):
        QuestionFreeText(**invalid_question)
    # should raise an exception if unexpected attribute is present
    invalid_question = valid_question.copy()
    invalid_question.update({"unexpected_attribute": "unexpected_attribute"})
    with pytest.raises(Exception):
        QuestionFreeText(**invalid_question)


def test_QuestionFreeText_serialization():
    """Test QuestionFreeText serialization."""

    # serialization should add a "type" attribute
    q = QuestionFreeText(**valid_question)
    assert q.to_dict() == {
        "question_name": "how_are_you",
        "question_text": "How are you?",
        "allow_nonresponse": False,
        "question_type": "free_text",
    }

    # deserialization should return a QuestionFreeTextEnhanced object
    q_lazarus = Question.from_dict(q.to_dict())
    assert isinstance(q_lazarus, QuestionFreeText)
    assert type(q) == type(q_lazarus)
    assert repr(q) == repr(q_lazarus)

    # serialization from bad data should raise an exception
    with pytest.raises(Exception):
        Question.from_dict({"type": "free_text"})
    with pytest.raises(Exception):
        Question.from_dict({"type": "free_text", "question_text": 1})
    with pytest.raises(Exception):
        Question.from_dict({"type": "free_text", "question_text": ""})
    with pytest.raises(Exception):
        Question.from_dict({"question_text": "Yo??"})


def test_QuestionFreeText_answers():
    q = QuestionFreeText(**valid_question)
    q_empty = QuestionFreeText(**valid_question_allow_nonresponse)
    response_good = {"answer": "I am doing ok.", "comment": "OK"}
    response_bad = {"answer": "I am doing ok.", "comment": "OK", "extra": "extra"}
    response_terrible = {"you": "suck"}

    # LLM responses are only required to have an "answer" key
    q.validate_answer(response_good)
    q.validate_answer(response_bad)
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer(response_terrible)

    # answer validation
    q.validate_answer(response_good)
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer(response_terrible)
    # with pytest.raises(QuestionAnswerValidationError):
    #     q.validate_answer({"answer": 1})

    # missing answer cases
    # with pytest.raises(QuestionAnswerValidationError):
    #     q.validate_answer({"answer": ""})
    # q_empty.validate_answer({"answer": ""})

    # code -> answer translation
    assert q.translate_answer_code_to_answer(response_good, None) == response_good


def test_test_QuestionFreeText_extras():
    """Test QuestionFreeText extra functionalities."""
    q = QuestionFreeText(**valid_question)
    # instructions
    assert "You are being asked" in q.instructions
    # simulate_answer
    simulated_answer = q.simulate_answer()
    assert isinstance(simulated_answer, dict)
    assert "answer" in simulated_answer
    assert isinstance(simulated_answer["answer"], str)
    assert len(simulated_answer["answer"]) <= Settings.MAX_ANSWER_LENGTH
    assert len(simulated_answer["answer"]) > 0
    # form elements

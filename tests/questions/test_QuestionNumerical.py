import pytest
from edsl.exceptions import QuestionAnswerValidationError
from edsl.questions import Question, Settings
from edsl.questions.QuestionNumerical import QuestionNumerical, main


def test_QuestionNumerical_main():
    main()


valid_question = {
    "question_text": "How many planets are there?",
    "question_name": "num_planets",
    "min_value": 1,
    "max_value": 10,
}

valid_question_wo_extras = {
    "question_text": "How many planets are there?",
    "question_name": "num_planets",
}


def test_QuestionNumerical_construction():
    """Test QuestionNumerical construction."""

    q = QuestionNumerical(**valid_question)
    assert isinstance(q, QuestionNumerical)
    assert q.question_name == valid_question["question_name"]
    assert q.question_text == valid_question["question_text"]
    assert q.min_value == valid_question["min_value"]
    assert q.max_value == valid_question["max_value"]

    assert q.data == valid_question

    # QuestionNumerical should impute extra fields appropriately
    q = QuestionNumerical(**valid_question_wo_extras)
    assert q.question_name == valid_question_wo_extras["question_name"]
    assert q.question_text == valid_question_wo_extras["question_text"]
    assert q.min_value == None
    assert q.max_value == None

    assert q.data != valid_question_wo_extras

    # should raise an exception if question_text is missing
    invalid_question = valid_question.copy()
    invalid_question.pop("question_text")
    with pytest.raises(Exception):
        QuestionNumerical(**invalid_question)
    # should raise an exception if question_text is empty
    invalid_question = valid_question.copy()
    invalid_question.update({"question_text": ""})
    with pytest.raises(Exception):
        QuestionNumerical(**invalid_question)
    # should raise an exception if question_text is too long
    invalid_question = valid_question.copy()
    invalid_question.update({"question_text": "a" * (Settings.MAX_QUESTION_LENGTH + 1)})
    with pytest.raises(Exception):
        QuestionNumerical(**invalid_question)
    # should raise an exception if unexpected attribute is present
    invalid_question = valid_question.copy()
    invalid_question.update({"unexpected_attribute": "unexpected_attribute"})
    with pytest.raises(Exception):
        QuestionNumerical(**invalid_question)
    # should raise an exception if min_value is not a number
    invalid_question = valid_question.copy()
    invalid_question.update({"min_value": "not a number"})
    with pytest.raises(Exception):
        QuestionNumerical(**invalid_question)


def test_QuestionNumerical_serialization():
    """Test QuestionNumerical serialization."""

    # serialization should add a "type" attribute
    q = QuestionNumerical(**valid_question)
    valid_question_w_type = valid_question.copy()
    valid_question_w_type.update({"question_type": "numerical"})
    assert q.to_dict() == valid_question_w_type
    # and optional attributes if not present
    q = QuestionNumerical(**valid_question_wo_extras)
    valid_question_wo_extras_w_type = valid_question_wo_extras.copy()
    valid_question_wo_extras_w_type.update(
        {"question_type": "numerical", "min_value": None, "max_value": None}
    )
    assert q.to_dict() == valid_question_wo_extras_w_type
    # deserialization should return a QuestionNumericalEnhanced object
    q_lazarus = Question.from_dict(q.to_dict())
    assert isinstance(q_lazarus, QuestionNumerical)
    assert type(q) == type(q_lazarus)
    assert repr(q) == repr(q_lazarus)

    # serialization from bad data should raise an exception
    with pytest.raises(Exception):
        Question.from_dict({"question_type": "numerical"})
    with pytest.raises(Exception):
        Question.from_dict({"question_type": "list", "question_text": 1})
    with pytest.raises(Exception):
        Question.from_dict({"question_type": "list", "question_text": ""})
    with pytest.raises(Exception):
        Question.from_dict(
            {"question_type": "list", "question_text": "", "min_value": "0"}
        )
    with pytest.raises(Exception):
        Question.from_dict(
            {"question_type": "list", "question_text": "Asd", "min_value": "yes"}
        )
    with pytest.raises(Exception):
        Question.from_dict(
            {
                "question_type": "list",
                "question_text": "Asd",
                "min_value": 4,
                "tires": 4,
            }
        )


def test_QuestionNumerical_answers():
    q = QuestionNumerical(**valid_question)
    response_good = {
        "answer": 5,
        "comment": "You got this!",
    }
    response_bad = {
        "answer": "Albuquerque",
        "comment": "OK",
        "extra": "extra",
    }
    response_terrible = {"you": "will never be able to do this!"}

    # LLM responses are required to have an "answer" key
    q.validate_answer(response_good)
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer(response_terrible)
    # and a numerical value
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer(response_bad)

    # answer validation
    q.validate_answer(response_good)
    q.validate_answer({"answer": "5"})
    q.validate_answer({"answer": "5.555"})
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer(response_terrible)

    # min/max value validation
    q.validate_answer({"answer": 1})
    q.validate_answer({"answer": 10})
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer({"answer": 0})
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer({"answer": 11})

    # missing answer cases
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer({"answer": ""})

    # wrong answer type
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer({"answer": None})
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer({"answer": []})
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer({"answer": "yooooooooo"})
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer({"answer": [{"answer": "yooooooooo"}]})
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer({"answer": [""]})

    # code -> answer translation
    assert q.translate_answer_code_to_answer(response_good, None) == response_good


def test_test_QuestionNumerical_extras():
    """Test QuestionNumerical extra functionalities."""
    q = QuestionNumerical(**valid_question)
    # instructions
    assert "You are being asked a question" in q.instructions
    # simulate_answer
    simulated_answer = q.simulate_answer()
    assert isinstance(simulated_answer, dict)
    assert "answer" in simulated_answer
    assert isinstance(simulated_answer["answer"], float)

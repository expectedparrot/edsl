import pytest
import uuid
from edsl.exceptions import (
    QuestionAnswerValidationError,
)
from edsl.questions import Question, Settings
from edsl.questions.QuestionCheckBox import QuestionCheckBox, main


def test_QuestionCheckBox_main():
    main()


valid_question = {
    "question_text": "Which weekdays do you like? Select 2 or 3.",
    "question_options": ["Mon", "Tue", "Wed", "Thu", "Fri"],
    "min_selections": 2,
    "max_selections": 3,
    "question_name": "weekdays",
    "short_names_dict": {},
}

valid_question_wo_extras = {
    "question_text": "Which weekdays do you like? Select 2 or 3.",
    "question_options": ["Mon", "Tue", "Wed", "Thu", "Fri"],
    "question_name": "weekdays",
    "short_names_dict": {},
}


def test_QuestionCheckBox_construction():
    """Test QuestionCheckBox construction."""

    q = QuestionCheckBox(**valid_question)
    assert isinstance(q, QuestionCheckBox)
    assert q.question_name == valid_question["question_name"]
    assert q.question_text == valid_question["question_text"]
    assert q.question_options == valid_question["question_options"]
    assert q.min_selections == valid_question["min_selections"]
    assert q.max_selections == valid_question["max_selections"]

    assert q.data == valid_question

    q_noextras = QuestionCheckBox(**valid_question_wo_extras)
    assert isinstance(q_noextras, QuestionCheckBox)
    assert q_noextras.question_name == valid_question["question_name"]
    assert q_noextras.question_text == valid_question["question_text"]
    assert q_noextras.question_options == valid_question["question_options"]
    # assert q_noextras.uuid is not None
    # should add extra attrs with None values
    assert q_noextras.min_selections == None
    assert q_noextras.max_selections == None

    # should raise an exception if question_text is missing
    invalid_question = valid_question.copy()
    invalid_question.pop("question_text")
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)

    # should raise an exception if question_text is empty
    invalid_question = valid_question.copy()
    invalid_question.update({"question_text": ""})
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)

    # should raise an exception if question_text is too long
    invalid_question = valid_question.copy()
    invalid_question.update({"question_text": "a" * (Settings.MAX_QUESTION_LENGTH + 1)})
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)

    # should raise an exception if question_options is missing
    invalid_question = valid_question.copy()
    invalid_question.pop("question_options")
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)

    # should raise an exception if question_options is empty
    invalid_question = valid_question.copy()
    invalid_question.update({"question_options": []})
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)
    invalid_question.update({"question_options": ["OK"]})
    # or has 1 item
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)
    # or has duplicates
    invalid_question.update({"question_options": ["OK", "OK"]})
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)
    # or has too many items
    invalid_question.update(
        {
            "question_options": [
                str(uuid.uuid4()) for _ in range(Settings.MAX_NUM_OPTIONS + 1)
            ]
        }
    )
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)
    # or not of type list of strings
    invalid_question.update({"question_options": [1, 2]})
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)
    invalid_question.update({"question_options": ["OK", 2]})
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)
    invalid_question.update({"question_options": ["OK", ""]})
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)
    invalid_question.update({"question_options": {"OK": "OK", "BAD": "BAD"}})
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)

    # should raise an exception if len(question_options) < min_selections
    invalid_question = valid_question.copy()
    invalid_question.update({"min_selections": 20})
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)
    # should raise an exception if len(question_options) < max_selections
    invalid_question = valid_question.copy()
    invalid_question.update({"max_selections": 20})
    with pytest.raises(Exception):
        QuestionCheckBox(**invalid_question)


def test_QuestionCheckBox_serialization():
    """Test QuestionCheckBox serialization."""
    q = QuestionCheckBox(**valid_question)
    q_noextras = QuestionCheckBox(**valid_question_wo_extras)

    # serialization should add a "type" attribute
    assert q.to_dict() == {
        "question_name": "weekdays",
        "question_text": "Which weekdays do you like? Select 2 or 3.",
        "question_options": ["Mon", "Tue", "Wed", "Thu", "Fri"],
        "min_selections": 2,
        "max_selections": 3,
        "question_type": "checkbox",
        "short_names_dict": {},
    }
    assert q_noextras.to_dict() == {
        "question_name": "weekdays",
        "question_text": "Which weekdays do you like? Select 2 or 3.",
        "question_options": ["Mon", "Tue", "Wed", "Thu", "Fri"],
        "min_selections": None,
        "max_selections": None,
        "question_type": "checkbox",
        "short_names_dict": {},
    }

    # deserialization should return a QuestionCheckBoxEnhanced object
    q_lazarus = Question.from_dict(q.to_dict())
    assert isinstance(q_lazarus, QuestionCheckBox)
    assert type(q) == type(q_lazarus)
    assert repr(q) == repr(q_lazarus)
    q_lazarus = Question.from_dict(q_noextras.to_dict())
    assert isinstance(q_lazarus, QuestionCheckBox)
    assert type(q_noextras) == type(q_lazarus)
    assert repr(q_noextras) == repr(q_lazarus)
    # serialization from bad data should raise an exception
    with pytest.raises(Exception):
        Question.from_dict({"type": "checkbox"})
    with pytest.raises(Exception):
        Question.from_dict({"type": "checkbox", "question_text": 1})
    with pytest.raises(Exception):
        Question.from_dict({"type": "checkbox", "question_text": ""})
    with pytest.raises(Exception):
        Question.from_dict(
            {
                "type": "checkbox",
                "question_text": "a" * (Settings.MAX_QUESTION_LENGTH + 1),
            }
        )
    with pytest.raises(Exception):
        Question.from_dict(
            {
                "type": "checkbox",
                "question_text": "Which weekdays do you like?",
                "question_options": [],
                "short_names_dict": {},
            }
        )
    with pytest.raises(Exception):
        Question.from_dict(
            {
                "type": "checkbox",
                "question_text": "Which weekdays do you like?",
                "question_options": ["Sun"],
                "short_names_dict": {},
            }
        )
    with pytest.raises(Exception):
        Question.from_dict(
            {
                "type": "checkbox",
                "question_text": "Which weekdays do you like?",
                "question_options": ["Sun", "Sun"],
                "short_names_dict": {},
            }
        )
    with pytest.raises(Exception):
        Question.from_dict(
            {
                "type": "checkbox",
                "question_text": "Which weekdays do you like?",
                "question_options": ["Mon", "Tue"],
                "min_selections": 3,
                "short_names_dict": {},
            }
        )
    with pytest.raises(Exception):
        Question.from_dict(
            {
                "type": "checkbox",
                "question_text": "Which weekdays do you like?",
                "question_options": ["Mon", "Tue"],
                "max_selections": 5,
                "short_names_dict": {},
            }
        )


def test_QuestionCheckBox_answers():
    q = QuestionCheckBox(**valid_question)
    llm_response_valid1 = {"answer": [0, 1], "comment": "I like beginnings"}
    llm_response_valid2 = {"answer": [0, 1]}
    llm_response_invalid1 = {"comment": "I like beginnings"}

    # LLM response is required to have an answer key, but is flexible otherwise
    q.validate_answer(llm_response_valid1)
    q.validate_answer(llm_response_valid2)
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer(llm_response_invalid1)

    # answer must be an list of ints
    q.validate_answer(llm_response_valid1)

    q.validate_answer(llm_response_valid2)
    # answer value required
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer({"answer": None})
    # answer cannot have unacceptable values
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer({"answer": [25, 20]})
    # or wrong types
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer({"answer": ["Mon", "Tue"]})
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer({"answer": [{"set"}]})
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer({"answer": {"answer": 0}})
    # and respect min_selections and max_selections
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer({"answer": [1]})
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer({"answer": [1, 2, 3, 4]})


def test_QuestionCheckBox_extras():
    """Test QuestionFreeText extra functionalities."""
    q = QuestionCheckBox(**valid_question)
    # translate_answer_code_to_answer
    assert q.translate_answer_code_to_answer([0, 1], None) == ["Mon", "Tue"]
    # instructions
    assert "You are being asked" in q.instructions
    # simulate_answer
    assert q.simulate_answer().keys() == q.simulate_answer(human_readable=True).keys()
    assert q.simulate_answer(human_readable=False)["answer"][0] in range(
        len(q.question_options)
    )
    simulated_answer = q.simulate_answer()
    assert isinstance(simulated_answer, dict)
    assert "answer" in simulated_answer
    assert "comment" in simulated_answer
    assert isinstance(simulated_answer["answer"], list)
    assert len(simulated_answer["answer"]) <= Settings.MAX_OPTION_LENGTH
    assert len(simulated_answer["answer"]) > 0

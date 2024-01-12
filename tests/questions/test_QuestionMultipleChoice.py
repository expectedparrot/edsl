import pytest
import uuid
from edsl.exceptions import QuestionAnswerValidationError
from edsl.questions import Question, Settings
from edsl.questions.QuestionMultipleChoice import QuestionMultipleChoice, main


def test_QuestionMultipleChoice_main():
    main()


valid_question = {
    "question_text": "How are you?",
    "question_options": ["OK", "Bad"],
    "question_name": "how_are_you",
    "short_names_dict": {},
}


def test_QuestionMultipleChoice_construction():
    """Test QuestionMultipleChoice construction."""

    q = QuestionMultipleChoice(**valid_question)
    assert isinstance(q, QuestionMultipleChoice)
    assert q.question_name == valid_question["question_name"]
    assert q.question_text == valid_question["question_text"]
    assert q.question_options == valid_question["question_options"]

    assert q.data == valid_question

    # should raise an exception if question_text is missing
    invalid_question = valid_question.copy()
    invalid_question.pop("question_text")
    with pytest.raises(Exception):
        QuestionMultipleChoice(**invalid_question)

    # should raise an exception if question_text is empty
    invalid_question = valid_question.copy()
    invalid_question.update({"question_text": ""})
    with pytest.raises(Exception):
        QuestionMultipleChoice(**invalid_question)

    # should raise an exception if question_text is too long
    invalid_question = valid_question.copy()
    invalid_question.update({"question_text": "a" * (Settings.MAX_QUESTION_LENGTH + 1)})
    with pytest.raises(Exception):
        QuestionMultipleChoice(**invalid_question)

    # should raise an exception if question_options is missing
    invalid_question = valid_question.copy()
    invalid_question.pop("question_options")
    with pytest.raises(Exception):
        QuestionMultipleChoice(**invalid_question)

    # should raise an exception if question_options is empty
    invalid_question = valid_question.copy()
    invalid_question.update({"question_options": []})
    with pytest.raises(Exception):
        QuestionMultipleChoice(**invalid_question)
    invalid_question.update({"question_options": ["OK"]})
    # or has 1 item
    with pytest.raises(Exception):
        QuestionMultipleChoice(**invalid_question)
    # or has duplicates
    invalid_question.update({"question_options": ["OK", "OK"]})
    with pytest.raises(Exception):
        QuestionMultipleChoice(**invalid_question)
    # or too many items
    invalid_question.update(
        {
            "question_options": [
                str(uuid.uuid4()) for _ in range(Settings.MAX_NUM_OPTIONS + 1)
            ]
        }
    )
    with pytest.raises(Exception):
        QuestionMultipleChoice(**invalid_question)
    # or not of type list of strings
    invalid_question.update({"question_options": [1, 2]})
    with pytest.raises(Exception):
        QuestionMultipleChoice(**invalid_question)
    invalid_question.update({"question_options": ["OK", 2]})
    with pytest.raises(Exception):
        QuestionMultipleChoice(**invalid_question)
    invalid_question.update({"question_options": ["OK", ""]})
    with pytest.raises(Exception):
        QuestionMultipleChoice(**invalid_question)

    invalid_question.update({"question_options": {"OK": "OK", "BAD": "BAD"}})
    with pytest.raises(Exception):
        QuestionMultipleChoice(**invalid_question)

    # should raise an exception if unexpected attribute is present
    invalid_question = valid_question.copy()
    invalid_question.update({"unexpected_attribute": "unexpected_attribute"})
    with pytest.raises(Exception):
        QuestionMultipleChoice(**invalid_question)

    # should raise an exception if question_name is a Python keyword
    invalid_question = valid_question.copy()
    invalid_question.update({"question_name": "for"})
    with pytest.raises(Exception):
        QuestionMultipleChoice(**invalid_question)
    invalid_question.update({"question_name": "!x12889"})
    with pytest.raises(Exception):
        QuestionMultipleChoice(**invalid_question)


def test_QuestionMultipleChoice_serialization():
    """Test QuestionMultipleChoice serialization."""

    # serialization should add a "type" attribute
    q = QuestionMultipleChoice(**valid_question)
    print(q.to_dict())
    assert q.to_dict() == {
        "question_name": "how_are_you",
        "question_text": "How are you?",
        "question_options": ["OK", "Bad"],
        "question_type": "multiple_choice",
        "short_names_dict": {},
    }

    # deserialization should return a QuestionMultipleChoiceEnhanced object
    q_lazarus = Question.from_dict(q.to_dict())
    assert isinstance(q_lazarus, QuestionMultipleChoice)
    assert type(q) == type(q_lazarus)
    assert repr(q) == repr(q_lazarus)

    # serialization from bad data should raise an exception
    with pytest.raises(Exception):
        Question.from_dict({"type": "multiple_choice"})
    with pytest.raises(Exception):
        Question.from_dict({"type": "multiple_choice", "question_text": 1})
    with pytest.raises(Exception):
        Question.from_dict({"type": "multiple_choice", "question_text": ""})
    with pytest.raises(Exception):
        Question.from_dict(
            {
                "type": "multiple_choice",
                "question_text": "a" * (Settings.MAX_QUESTION_LENGTH + 1),
            }
        )
    with pytest.raises(Exception):
        Question.from_dict(
            {
                "type": "multiple_choice",
                "question_text": "How are you?",
                "question_options": [],
            }
        )


def test_QuestionMultipleChoice_answers():
    q = QuestionMultipleChoice(**valid_question)
    llm_response_valid1 = {"answer": 0, "comment": "I'm good"}
    llm_response_valid2 = {"answer": 0}
    llm_response_invalid1 = {"comment": "I'm good"}

    # LLM response is required to have an answer key, but is flexible otherwise
    q.validate_answer(llm_response_valid1)
    q.validate_answer(llm_response_valid2)
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer(llm_response_invalid1)

    # answer must be an integer or interpretable as integer
    q.validate_answer({"answer": 0})
    # TODO: should the following three be allowed?
    q.validate_answer({"answer": "0"})
    q.validate_answer({"answer": True})
    q.validate_answer({"answer": 0, "comment": "I'm good"})
    # answer value required
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer({"answer": None})
    # answer must be in range of question_options
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer({"answer": "2"})
    # answer can't be a random string
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer({"answer": "asdf"})
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer({"answer": [0, 1]})
    with pytest.raises(QuestionAnswerValidationError):
        q.validate_answer({"answer": {"answer": 0}})


def test_QuestionMultipleChoice_extras():
    """Test QuestionFreeText extra functionalities."""
    q = QuestionMultipleChoice(**valid_question)
    # instructions
    assert "You are being asked" in q.instructions
    # translate answer code to answer
    assert q.translate_answer_code_to_answer(0, scenario=None) == "OK"
    assert q.translate_answer_code_to_answer(1, scenario=None) == "Bad"
    with pytest.raises(IndexError):
        q.translate_answer_code_to_answer(2, scenario=None)

    # simulate_answer
    assert q.simulate_answer().keys() == q.simulate_answer(human_readable=True).keys()
    assert q.simulate_answer(human_readable=False)["answer"] in range(
        len(q.question_options)
    )
    simulated_answer = q.simulate_answer()
    assert isinstance(simulated_answer, dict)
    assert "answer" in simulated_answer
    assert "comment" in simulated_answer
    assert isinstance(simulated_answer["answer"], str)
    assert len(simulated_answer["answer"]) <= Settings.MAX_ANSWER_LENGTH
    assert len(simulated_answer["answer"]) > 0
    assert simulated_answer["answer"] in q.question_options

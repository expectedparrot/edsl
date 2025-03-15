import pytest
from edsl.questions import QuestionBase
from edsl.questions.derived.question_likert_five import QuestionLikertFive


# def test_QuestionLikertFive_main():
#     main()


valid_question = {
    "question_text": "You like pizza. How strongly do you dis/agree?",
    "question_name": "pizza_love",
}

valid_question_w_extras = {
    "question_text": "Statement: Pizza is delicious.",
    "question_name": "pizza_love",
}


def test_QuestionLikertFive_construction():
    """Test QuestionLikertFive construction."""

    # QuestionLikertFive should impute extra fields appropriately
    q = QuestionLikertFive(**valid_question)
    assert isinstance(q, QuestionLikertFive)
    assert q.question_text == valid_question["question_text"]

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
    # assert q.question_options == valid_question_w_extras["question_options"]

    # assert q.data == valid_question_w_extras


def test_QuestionLikertFive_serialization():
    """Test QuestionLikertFive serialization."""

    # serialization should add a "type" attribute
    q = QuestionLikertFive(**valid_question)
    default_options = q.question_options
    assert {
        "question_text": valid_question["question_text"],
        "question_options": default_options,
        "question_name": "pizza_love",
        "question_type": "likert_five",
    }.items() <= q.to_dict().items()

    # deserialization should return a QuestionLikertFiveEnhanced object
    q_lazarus = QuestionBase.from_dict(q.to_dict())
    assert isinstance(q_lazarus, QuestionLikertFive)
    assert type(q) == type(q_lazarus)

    q_extras = QuestionLikertFive(**valid_question_w_extras)
    q_lazarus = QuestionBase.from_dict(q_extras.to_dict())
    assert repr(q_extras) == repr(q_lazarus)


def test_QuestionLikertFive_extras():
    """Test QuestionFreeText extra functionalities."""
    q = QuestionLikertFive(**valid_question)
    # instructions
    # form elements

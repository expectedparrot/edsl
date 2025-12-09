import pytest
from edsl.questions import QuestionBase, QuestionTopK


def test_QuestionTopK_main():
    # Commented out as main is no longer directly imported
    # main()
    pass


valid_question = {
    "question_text": "What are your 2 favorite foods in the list?",
    "question_options": ["Pizza", "Ice cream", "Cake", "Cereal"],
    "min_selections": 2,
    "max_selections": 2,
    "question_name": "food",
    "use_code": True,
}


def test_QuestionTopK_construction():
    """Test QuestionTopK construction."""

    q = QuestionTopK(**valid_question)
    assert isinstance(q, QuestionTopK)
    assert q.question_name == valid_question["question_name"]
    assert q.question_text == valid_question["question_text"]
    assert q.question_options == valid_question["question_options"]
    assert q.min_selections == valid_question["min_selections"]
    assert q.max_selections == valid_question["max_selections"]

    assert q.data == valid_question

    # should raise an exception if question_options is a list
    invalid_question = valid_question.copy()
    invalid_question.update({"question_options": "question_options"})
    with pytest.raises(Exception):
        QuestionTopK(**invalid_question)
    # or if it is a list but has len < 2
    invalid_question.update({"question_options": ["Pizza"]})
    with pytest.raises(Exception):
        QuestionTopK(**invalid_question)
    # or if it has repeated elements
    invalid_question.update({"question_options": ["Pizza", "Pizza"]})
    with pytest.raises(Exception):
        QuestionTopK(**invalid_question)
    # or too many elements
    # invalid_question.update(
    #     {
    #         "question_options": [
    #             str(uuid.uuid4()) for _ in range(Settings.MAX_NUM_OPTIONS + 1)
    #         ]
    #     }
    # )
    # with pytest.raises(Exception):
    #     QuestionTopK(**invalid_question)

    # should raise an exception if min_selections != max_selections
    invalid_question = valid_question.copy()
    invalid_question.update({"min_selections": 1, "max_selections": 2})
    with pytest.raises(Exception):
        QuestionTopK(**invalid_question)
    # or if it larger than the number of options
    invalid_question.update({"min_selections": 5, "max_selections": 5})
    with pytest.raises(Exception):
        QuestionTopK(**invalid_question)
    # or if it is smaller than 1
    invalid_question.update({"min_selections": 0, "max_selections": 0})
    with pytest.raises(Exception):
        QuestionTopK(**invalid_question)


def test_QuestionTopK_serialization():
    """Test QuestionTopK serialization."""

    # serialization should add a "type" attribute
    q = QuestionTopK(**valid_question)
    print(q.to_dict())
    assert {
        "question_name": "food",
        "question_text": "What are your 2 favorite foods in the list?",
        "question_options": ["Pizza", "Ice cream", "Cake", "Cereal"],
        "min_selections": 2,
        "max_selections": 2,
        "question_type": "top_k",
    }.items() <= q.to_dict().items()

    # deserialization should return a QuestionTopKEnhanced object
    q_lazarus = QuestionBase.from_dict(q.to_dict())
    assert isinstance(q_lazarus, QuestionTopK)
    assert type(q) == type(q_lazarus)
    assert repr(q) == repr(q_lazarus)

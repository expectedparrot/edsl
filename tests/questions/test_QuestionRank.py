import pytest
from edsl.questions.exceptions import (
    QuestionAnswerValidationError,
    QuestionResponseValidationError,
)
from edsl.questions import Settings
from edsl.questions import QuestionBase
from edsl.questions.question_rank import QuestionRank, main


def test_QuestionRank_main():
    main()


valid_question = {
    "question_text": "What are your 2 favorite foods in the list, ranked?",
    "question_options": ["Pizza", "Ice cream", "Cake", "Cereal"],
    "question_name": "food",
    "num_selections": 2,
    "use_code": True,
}

valid_question_wo_extras = {
    "question_text": "What are your 2 favorite foods in the list, ranked?",
    "question_options": ["Pizza", "Ice cream", "Cake", "Cereal"],
    "question_name": "food",
}


def test_QuestionRank_construction():
    """Test QuestionRank construction."""

    q = QuestionRank(**valid_question)
    assert isinstance(q, QuestionRank)
    assert q.question_name == valid_question["question_name"]
    assert q.question_text == valid_question["question_text"]
    assert q.question_options == valid_question["question_options"]
    assert q.num_selections == valid_question["num_selections"]

    assert q.data == valid_question

    # QuestionRank should impute extra fields appropriately
    q = QuestionRank(**valid_question_wo_extras)
    assert q.question_name == valid_question["question_name"]
    assert q.question_text == valid_question["question_text"]
    assert q.question_options == valid_question["question_options"]
    assert q.num_selections == 4

    assert q.data != valid_question_wo_extras
    assert q.data != valid_question

    # should raise an exception if question_text is missing
    invalid_question = valid_question.copy()
    invalid_question.pop("question_text")
    with pytest.raises(Exception):
        QuestionRank(**invalid_question)
    # should raise an exception if question_text is empty
    invalid_question = valid_question.copy()
    invalid_question.update({"question_text": ""})
    with pytest.raises(Exception):
        QuestionRank(**invalid_question)
    # should raise an exception if question_text is too long
    invalid_question = valid_question.copy()
    from edsl.questions.settings import Settings

    # invalid_question.update({"question_text": "a" * (Settings.MAX_QUESTION_LENGTH + 1)})
    # with pytest.raises(Exception):
    #     QuestionRank(**invalid_question)
    # should raise an exception if unexpected attribute is present
    invalid_question = valid_question.copy()
    invalid_question.update({"unexpected_attribute": "unexpected_attribute"})
    with pytest.raises(Exception):
        QuestionRank(**invalid_question)
    # should raise an exception if len(question_options) < num_selections
    invalid_question = valid_question.copy()
    invalid_question.update({"num_selections": 5})
    with pytest.raises(Exception):
        QuestionRank(**invalid_question)
    # should raise an exception if options are not unique
    invalid_question = valid_question.copy()
    invalid_question.update({"question_options": ["Pizza", "Pizza", "Cake", "Cereal"]})
    with pytest.raises(Exception):
        QuestionRank(**invalid_question)
    # should raise an exception if options are too long
    invalid_question = valid_question.copy()

    with pytest.raises(Exception):
        from edsl.questions.settings import Settings

        invalid_question.update(
            {
                "question_options": [
                    "Pizza",
                    "Ice cream",
                    "Cake",
                    "Cereal" * (1 + Settings.MAX_OPTION_LENGTH),
                ]
            }
        )
        QuestionRank(**invalid_question)


def test_QuestionRank_serialization():
    """Test QuestionRank serialization."""

    # serialization should add a "type" attribute
    q = QuestionRank(**valid_question)
    valid_question_w_type = valid_question.copy()
    valid_question_w_type.update({"question_type": "rank"})
    assert valid_question_w_type.items() <= q.to_dict().items()
    q = QuestionRank(**valid_question_wo_extras)
    valid_question_w_type = valid_question_wo_extras.copy()
    valid_question_w_type.update({"question_type": "rank", "num_selections": 4})
    assert valid_question_w_type.items() <= q.to_dict().items()

    # deserialization should return a QuestionRankEnhanced object
    q_lazarus = QuestionBase.from_dict(q.to_dict())
    assert isinstance(q_lazarus, QuestionRank)
    assert type(q) == type(q_lazarus)
    assert repr(q) == repr(q_lazarus)

    # serialization from bad data should raise an exception
    with pytest.raises(Exception):
        QuestionBase.from_dict({"question_type": "rank"})
    with pytest.raises(Exception):
        QuestionBase.from_dict({"question_type": "rank", "question_text": 1})
    with pytest.raises(Exception):
        QuestionBase.from_dict({"question_type": "rank", "question_text": ""})
    with pytest.raises(Exception):
        QuestionBase.from_dict(
            {
                "question_type": "list",
                "question_text": "What are your 2 favorite foods in the list, ranked?",
                "question_options": ["Pizza", "Ice cream", "Cake", "Cereal"],
                "num_selections": 52,
            }
        )
    with pytest.raises(Exception):
        QuestionBase.from_dict(
            {
                "question_type": "list",
                "question_text": "What are your 2 favorite foods in the list, ranked?",
                "question_options": ["Pizza", "Ice cream", "Cake", "Cereal"],
                "num_selections": 3,
                "kirby": "is cute",
            }
        )


def test_QuestionRank_answers():
    q = QuestionRank(**valid_question)
    response_good = {
        "answer": [2, 1],
        "comment": "You got this!",
    }
    response_bad = {
        "answer": [2, 1],
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
    q._validate_answer({"answer": [2, 1]})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer(response_terrible)
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": 1})

    # missing answer
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": []})

    # answer not in options
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": [5, 1]})

    # not enough answers
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": [1]})

    # too many answers
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": [3, 2, 1]})

    # wrong answer type
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": ["Ice cream", "Pizza"]})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": [{"answer": "yooooooooo"}]})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": [""]})

    # code -> answer translation
    assert q._translate_answer_code_to_answer(response_good["answer"], None) == [
        "Cake",
        "Ice cream",
    ]


def test_QuestionRank_extras():
    """Test QuestionFreeText extra functionalities."""
    q = QuestionRank(**valid_question)
    # instructions
    # _simulate_answer
    assert q._simulate_answer().keys() == q._simulate_answer(human_readable=True).keys()
    assert q._simulate_answer(human_readable=False)["answer"][0] in range(
        len(q.question_options)
    )
    simulated_answer = q._simulate_answer()
    assert isinstance(simulated_answer, dict)
    assert "answer" in simulated_answer
    assert "comment" in simulated_answer
    assert isinstance(simulated_answer["answer"], list)
    assert len(simulated_answer["answer"]) > 0
    assert len(str(simulated_answer["answer"][0])) <= Settings.MAX_ANSWER_LENGTH

    simulated_answer = q._simulate_answer(human_readable=True)
    assert simulated_answer["answer"][0] in q.question_options

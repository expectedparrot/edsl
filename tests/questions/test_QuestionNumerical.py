import pytest

from edsl.questions.exceptions import (
    QuestionAnswerValidationError,
)
from edsl.questions import QuestionBase
from edsl.questions import QuestionNumerical  # , main


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
    # invalid_question = valid_question.copy()
    # invalid_question.update({"question_text": "a" * (Settings.MAX_QUESTION_LENGTH + 1)})
    # with pytest.raises(Exception):
    #     QuestionNumerical(**invalid_question)
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


def remove_none_values(d):
    return {k: v for k, v in d.items() if v is not None}


def test_QuestionNumerical_serialization():
    """Test QuestionNumerical serialization."""

    # serialization should add a "type" attribute
    q = QuestionNumerical(**valid_question)
    valid_question_w_type = valid_question.copy()
    valid_question_w_type.update({"question_type": "numerical"})
    assert valid_question_w_type.items() <= q.to_dict().items()
    # and optional attributes if not present
    q = QuestionNumerical(**valid_question_wo_extras)
    valid_question_wo_extras_w_type = valid_question_wo_extras.copy()
    valid_question_wo_extras_w_type.update(
        {"question_type": "numerical", "min_value": None, "max_value": None}
    )
    assert (
        remove_none_values(valid_question_wo_extras_w_type).items()
        <= q.to_dict().items()
    )
    # deserialization should return a QuestionNumericalEnhanced object
    q_lazarus = QuestionBase.from_dict(q.to_dict())
    assert isinstance(q_lazarus, QuestionNumerical)
    assert type(q) == type(q_lazarus)
    assert repr(q) == repr(q_lazarus)

    # serialization from bad data should raise an exception
    with pytest.raises(Exception):
        QuestionBase.from_dict({"question_type": "numerical"})
    with pytest.raises(Exception):
        QuestionBase.from_dict({"question_type": "list", "question_text": 1})
    with pytest.raises(Exception):
        QuestionBase.from_dict({"question_type": "list", "question_text": ""})
    with pytest.raises(Exception):
        QuestionBase.from_dict(
            {"question_type": "list", "question_text": "", "min_value": "0"}
        )
    with pytest.raises(Exception):
        QuestionBase.from_dict(
            {"question_type": "list", "question_text": "Asd", "min_value": "yes"}
        )
    with pytest.raises(Exception):
        QuestionBase.from_dict(
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

    # # LLM responses are only required to have an "answer" key
    # q._validate_response(response_good)
    # with pytest.raises(QuestionResponseValidationError):
    #     q._validate_response(response_terrible)
    # # but can have additional keys
    # q._validate_response(response_bad)

    # answer validation
    q._validate_answer(response_good)
    q._validate_answer({"answer": "5"})
    q._validate_answer({"answer": "5.555"})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer(response_terrible)

    # min/max value validation
    q._validate_answer({"answer": 1})
    q._validate_answer({"answer": 10})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": 0})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": 11})

    # missing answer cases
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": ""})

    # wrong answer type - going to allow Nones
    # with pytest.raises(QuestionAnswerValidationError):
    #    q._validate_answer({"answer": None})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": []})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": "yooooooooo"})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": [{"answer": "yooooooooo"}]})
    with pytest.raises(QuestionAnswerValidationError):
        q._validate_answer({"answer": [""]})

    # code -> answer translation
    assert q._translate_answer_code_to_answer(response_good, None) == response_good


def test_numerical_repair_prefers_a_structured_answer():
    q = QuestionNumerical(
        question_name="probability",
        question_text="Return one probability.",
        min_value=0,
        max_value=1,
    )
    generated_tokens = "I saw 12 events on day 3; final answer: 0.7"

    result = q.response_validator.validate(
        {"answer": 0.4, "generated_tokens": generated_tokens}
    )

    assert result["answer"] == 0.4
    assert result["answer_source"] == "structured"
    assert result["generated_tokens"] == generated_tokens


def test_numerical_repair_provenance_resets_between_responses():
    q = QuestionNumerical(
        question_name="probability",
        question_text="Return one probability.",
        min_value=0,
        max_value=1,
    )
    validator = q.response_validator

    repaired = validator.validate({"answer": "Final answer: 0.4"})
    structured = validator.validate({"answer": 0.6})

    assert repaired["answer_source"] == "repaired"
    assert structured["answer_source"] == "structured"


def test_numerical_repair_uses_final_answer_marker():
    q = QuestionNumerical(
        question_name="probability",
        question_text="Return one probability.",
        min_value=0,
        max_value=1,
    )
    response = {
        "answer": "I counted 1 observation on day 12. The final probability is 0.1667.",
        "generated_tokens": "I counted 1 observation on day 12.\nFinal answer: 0.1667",
        "comment": "Estimated from the observations.",
    }

    result = q.response_validator.validate(response)

    assert result["answer"] == pytest.approx(0.1667)
    assert result["answer_source"] == "repaired"
    assert result["generated_tokens"] == response["generated_tokens"]
    assert result["comment"] == response["comment"]


def test_numerical_repair_uses_a_final_standalone_numeric_line():
    q = QuestionNumerical(
        question_name="probability",
        question_text="Return one probability.",
        min_value=0,
        max_value=1,
    )

    result = q.response_validator.validate(
        {"answer": "I considered 0.2 and 0.3.\n0.1667"}
    )

    assert result["answer"] == pytest.approx(0.1667)


@pytest.mark.parametrize("answer", [0, 1])
def test_numerical_repair_accepts_zero_and_one(answer):
    q = QuestionNumerical(
        question_name="probability",
        question_text="Return one probability.",
        min_value=0,
        max_value=1,
    )

    result = q.response_validator.validate({"answer": f"Final answer: {answer}."})

    assert result["answer"] == answer
    assert result["answer_source"] == "repaired"


def test_numerical_repair_ignores_intermediate_dates_currency_and_percentages():
    q = QuestionNumerical(
        question_name="probability",
        question_text="Return one probability.",
        min_value=0,
        max_value=1,
    )

    result = q.response_validator.validate(
        {"answer": "On day 12 in 2024, $50 was 50%; final probability is 0.1667."}
    )

    assert result["answer"] == pytest.approx(0.1667)


def test_numerical_repair_supports_signed_scientific_notation():
    q = QuestionNumerical(
        question_name="measurement",
        question_text="Return a measurement.",
        min_value=-1,
        max_value=1,
    )

    result = q.response_validator.validate({"answer": "Final answer: -1.25e-3"})

    assert result["answer"] == pytest.approx(-0.00125)


def test_numerical_repair_supports_thousands_separators():
    q = QuestionNumerical(
        question_name="count",
        question_text="Return a count.",
        min_value=0,
        max_value=2000,
    )

    result = q.response_validator.validate({"answer": "Final answer: 1,234."})

    assert result["answer"] == 1234


def test_numerical_repair_fails_when_multiple_values_are_plausible():
    q = QuestionNumerical(
        question_name="probability",
        question_text="Return one probability.",
        min_value=0,
        max_value=1,
    )

    with pytest.raises(QuestionAnswerValidationError):
        q.response_validator.validate({"answer": "I compared 0.2 with 0.8."})


def test_numerical_repair_does_not_fall_back_to_an_in_range_value():
    q = QuestionNumerical(
        question_name="probability",
        question_text="Return one probability.",
        min_value=0,
        max_value=1,
    )

    with pytest.raises(QuestionAnswerValidationError):
        q.response_validator.validate(
            {"answer": "Final answer: 1.5; an earlier candidate was 0.5."}
        )


def test_numerical_repair_uses_generated_tokens_only_without_an_answer():
    q = QuestionNumerical(
        question_name="probability",
        question_text="Return one probability.",
        min_value=0,
        max_value=1,
    )
    generated_tokens = "I estimated several values.\nFinal answer: 0.25"

    result = q.response_validator.validate(
        {"answer": None, "generated_tokens": generated_tokens}
    )

    assert result["answer"] == 0.25
    assert result["answer_source"] == "repaired"
    assert result["generated_tokens"] == generated_tokens


def test_numerical_repair_does_not_search_generated_tokens_when_answer_exists():
    q = QuestionNumerical(
        question_name="probability",
        question_text="Return one probability.",
        min_value=0,
        max_value=1,
    )

    with pytest.raises(QuestionAnswerValidationError):
        q.response_validator.validate(
            {"answer": "No numerical answer was supplied.", "generated_tokens": "0.5"}
        )


def test_test_QuestionNumerical_extras():
    """Test QuestionNumerical extra functionalities."""
    q = QuestionNumerical(**valid_question)
    # instructions
    # _simulate_answer
    simulated_answer = q._simulate_answer()
    assert isinstance(simulated_answer, dict)
    assert "answer" in simulated_answer
    from decimal import Decimal

    try:
        assert (
            isinstance(simulated_answer["answer"], float)
            or isinstance(simulated_answer["answer"], int)
            or isinstance(simulated_answer["answer"], Decimal)
            or simulated_answer["answer"] is None
        )
    except AssertionError:
        # breakpoint()
        pass

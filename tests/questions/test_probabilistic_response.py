import math

import pytest

from edsl import Model, ProbabilisticResponse, QuestionMultipleChoice, Results
from edsl.questions.exceptions import QuestionAnswerValidationError
from edsl.questions.question_base import QuestionBase


def make_question(**contract_kwargs):
    return QuestionMultipleChoice(
        question_name="trust",
        question_text="How much trust?",
        question_options=["High", "Medium", "Low"],
        probabilistic_response=ProbabilisticResponse(**contract_kwargs),
    )


def test_contract_and_question_round_trip():
    question = make_question(resolution="sample", seed=42)
    serialized = question.to_dict(add_edsl_version=False)

    assert serialized["probabilistic_response"] == {
        "representation": "categorical",
        "resolution": "sample",
        "seed": 42,
        "tolerance": 1e-6,
    }
    restored = QuestionBase.from_dict(serialized)
    assert restored.probabilistic_response == question.probabilistic_response


def test_response_model_requests_probabilities_in_answer_object():
    schema = make_question(resolution="none").response_model.model_json_schema()
    answer_schema = schema["properties"]["answer"]
    assert "$ref" in answer_schema
    assert "probabilities" in str(schema)


def test_none_retains_distribution_without_answer():
    validated = make_question(resolution="none")._validate_answer(
        {"answer": {"probabilities": [0.1, 0.35, 0.55]}}
    )
    assert validated["answer"] is None
    assert validated["distribution"] == [0.1, 0.35, 0.55]
    assert validated["resolution_method"] == "none"
    assert validated["resolution_draw"] is None


def test_sample_is_seeded_and_preserves_audit_trail():
    question = make_question(resolution="sample", seed=42)
    first = question._validate_answer(
        {"answer": {"probabilities": [0.1, 0.35, 0.55]}}
    )
    second = question._validate_answer(
        {"answer": {"probabilities": [0.1, 0.35, 0.55]}}
    )

    assert first == second
    assert first["answer"] == "Low"
    assert first["resolution_seed"] == 42
    assert first["resolution_method"] == "sample"
    assert math.isclose(first["resolution_draw"], 0.6394267984578837)


def test_mode_is_explicit_and_uses_first_option_for_ties():
    result = make_question(resolution="mode")._validate_answer(
        {"answer": {"probabilities": [0.45, 0.45, 0.1]}}
    )
    assert result["answer"] == "High"
    assert result["resolution_method"] == "mode"
    assert result["resolution_draw"] is None


@pytest.mark.parametrize(
    "probabilities",
    [
        [0.5, 0.5],
        [0.5, -0.1, 0.6],
        [0.2, 0.2, 0.2],
        [0.0, float("nan"), 1.0],
        [True, 0.0, 0.0],
    ],
)
def test_invalid_probability_vectors_are_rejected(probabilities):
    with pytest.raises(QuestionAnswerValidationError):
        make_question(resolution="none")._validate_answer(
            {"answer": {"probabilities": probabilities}}
        )


def test_use_code_resolves_to_ordinary_code():
    question = QuestionMultipleChoice(
        question_name="trust",
        question_text="How much trust?",
        question_options=["High", "Medium", "Low"],
        use_code=True,
        probabilistic_response=ProbabilisticResponse(resolution="mode"),
    )
    result = question._validate_answer(
        {"answer": {"probabilities": [0.1, 0.8, 0.1]}}
    )
    assert result["answer"] == 1


def test_repeated_resolution_reuses_distribution():
    contract = ProbabilisticResponse(resolution="sample", seed=7)
    draws = contract.resolve([0.25, 0.75], n=3, seed=20260725)
    assert len(draws) == 3
    assert all(draw["method"] == "sample" for draw in draws)
    assert draws == contract.resolve([0.25, 0.75], n=3, seed=20260725)


def test_sample_requires_seed():
    with pytest.raises(ValueError, match="explicit seed"):
        ProbabilisticResponse(resolution="sample")


def test_local_job_retains_resolution_audit_fields_and_round_trips():
    question = QuestionMultipleChoice(
        question_name="trust",
        question_text="How much trust?",
        question_options=["High", "Low"],
        probabilistic_response=ProbabilisticResponse(resolution="sample", seed=42),
    )
    results = question.by(
        Model("test", canned_response='{"probabilities":[0.1,0.9]}')
    ).run(disable_remote_inference=True)

    row = results.select(
        "answer.trust",
        "distribution.trust_distribution",
        "resolution_draw.trust_resolution_draw",
        "resolution_seed.trust_resolution_seed",
        "resolution_method.trust_resolution_method",
    ).to_list()[0]
    assert row == ("Low", [0.1, 0.9], 0.6394267984578837, 42, "sample")

    restored = Results.from_dict(results.to_dict())
    assert restored.select(
        "distribution.trust_distribution",
        "resolution_method.trust_resolution_method",
    ).to_list() == [([0.1, 0.9], "sample")]


def test_prompt_requests_probabilities_without_model_generated_randomness():
    prompt = make_question(resolution="sample", seed=42).prompt_preview().text
    assert '"probabilities" array' in prompt
    assert "Do not choose an option or generate a random draw." in prompt

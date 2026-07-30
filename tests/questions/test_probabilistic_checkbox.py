import pytest

from edsl import Model, ProbabilisticResponse, QuestionCheckBox, Results
from edsl.questions.exceptions import QuestionAnswerValidationError
from edsl.questions.question_base import QuestionBase


def make_contract(resolution="none", seed=None):
    return ProbabilisticResponse(
        representation="inclusion_probabilities",
        joint_model="independent",
        resolution=resolution,
        seed=seed,
    )


def make_question(**contract_kwargs):
    return QuestionCheckBox(
        question_name="services",
        question_text="Which services would you use?",
        question_options=["Library", "Transit", "Parks"],
        probabilistic_response=make_contract(**contract_kwargs),
    )


def test_checkbox_contract_requires_explicit_independence():
    with pytest.raises(ValueError, match="joint_model='independent'"):
        ProbabilisticResponse(representation="inclusion_probabilities")


@pytest.mark.parametrize(
    "constraint",
    [{"min_selections": 1}, {"max_selections": 2}],
)
def test_selection_constraints_are_rejected(constraint):
    with pytest.raises(ValueError, match="change the supplied marginal"):
        QuestionCheckBox(
            question_name="services",
            question_text="Which services would you use?",
            question_options=["Library", "Transit", "Parks"],
            probabilistic_response=make_contract(),
            **constraint,
        )


def test_question_round_trip():
    question = make_question(resolution="sample", seed=42)
    restored = QuestionBase.from_dict(question.to_dict())
    assert restored.probabilistic_response == question.probabilistic_response


def test_none_retains_marginals_without_subset():
    result = make_question()._validate_answer(
        {"answer": {"inclusion_probabilities": [0.8, 0.2, 0.5]}}
    )
    assert result["answer"] is None
    assert result["distribution"] == [0.8, 0.2, 0.5]
    assert result["resolution_method"] == "none"


def test_seeded_independent_bernoulli_resolution():
    result = make_question(resolution="sample", seed=42)._validate_answer(
        {"answer": {"inclusion_probabilities": [0.5, 0.1, 0.2]}}
    )
    assert result["answer"] == ["Transit"]
    assert result["resolution_draw"] == [
        0.6394267984578837,
        0.025010755222666936,
        0.27502931836911926,
    ]
    assert result["resolution_seed"] == 42
    assert result["resolution_method"] == "sample"


def test_explicit_mode_uses_half_probability_threshold():
    result = make_question(resolution="mode")._validate_answer(
        {"answer": {"inclusion_probabilities": [0.5, 0.49, 0.9]}}
    )
    assert result["answer"] == ["Library", "Parks"]
    assert result["resolution_draw"] is None


def test_use_code_returns_indices():
    question = QuestionCheckBox(
        question_name="services",
        question_text="Which services would you use?",
        question_options=["Library", "Transit", "Parks"],
        use_code=True,
        probabilistic_response=make_contract(resolution="mode"),
    )
    result = question._validate_answer(
        {"answer": {"inclusion_probabilities": [0.1, 0.8, 0.7]}}
    )
    assert result["answer"] == [1, 2]


@pytest.mark.parametrize(
    "probabilities",
    [
        [0.1, 0.2],
        [0.1, -0.1, 1.0],
        [0.1, 1.1, 0.0],
        [0.1, float("inf"), 0.0],
        [True, 0.0, 0.0],
    ],
)
def test_invalid_inclusion_probabilities_are_rejected(probabilities):
    with pytest.raises(QuestionAnswerValidationError):
        make_question()._validate_answer(
            {"answer": {"inclusion_probabilities": probabilities}}
        )


def test_boundary_probabilities_resolve_deterministically():
    contract = make_contract(resolution="sample", seed=7)
    draws = contract.resolve([0.0, 1.0, 0.0, 1.0], n=100)
    assert all(draw["indices"] == [1, 3] for draw in draws)


def test_checkbox_response_seed_is_agent_specific():
    contract = make_contract(resolution="sample", seed=7)
    ada = contract.resolve(
        [0.5, 0.5], context={"agent": {"name": "Ada"}, "question": "services"}
    )[0]
    grace = contract.resolve(
        [0.5, 0.5], context={"agent": {"name": "Grace"}, "question": "services"}
    )[0]
    assert ada["seed"] != grace["seed"]
    assert ada["draw"] != grace["draw"]


def test_local_job_retains_checkbox_audit_fields_and_round_trips():
    question = make_question(resolution="sample", seed=42)
    results = question.by(
        Model(
            "test",
            canned_response='{"inclusion_probabilities":[0.5,0.1,0.2]}',
        )
    ).run(disable_remote_inference=True)

    answer, probabilities, draws, method = results.select(
        "answer.services",
        "distribution.services_distribution",
        "resolution_draw.services_resolution_draw",
        "resolution_method.services_resolution_method",
    ).to_list()[0]
    assert probabilities == [0.5, 0.1, 0.2]
    assert answer == [
        option
        for option, draw, probability in zip(
            ["Library", "Transit", "Parks"], draws, probabilities
        )
        if draw < probability
    ]
    assert len(draws) == 3
    assert all(0 <= draw < 1 for draw in draws)
    assert method == "sample"

    restored = Results.from_dict(results.to_dict())
    assert restored.select(
        "distribution.services_distribution"
    ).to_list() == [[0.5, 0.1, 0.2]]
    assert restored.select(
        "resolution_seed.services_resolution_seed"
    ).to_list()[0] != 42


def test_prompt_discloses_independence_assumption():
    prompt = make_question(resolution="sample", seed=42).prompt_preview().text
    assert '"inclusion_probabilities" array' in prompt
    assert "independent Bernoulli selections" in prompt

import math

import pytest

from edsl import (
    Agent,
    AgentList,
    Model,
    ProbabilisticResponse,
    QuestionMultipleChoice,
    Results,
    Scenario,
    Survey,
)
from edsl.invigilators import InvigilatorHuman
from edsl.surveys.memory import MemoryPlan
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


def test_response_seed_is_stable_and_context_specific():
    contract = ProbabilisticResponse(resolution="sample", seed=42)
    first_context = {
        "agent": {"name": "Ada", "age": 34},
        "scenario": {"city": "Boston"},
        "question": "trust",
        "iteration": 0,
    }
    reordered_context = {
        "iteration": 0,
        "question": "trust",
        "scenario": {"city": "Boston"},
        "agent": {"age": 34, "name": "Ada"},
    }
    other_agent_context = {
        **first_context,
        "agent": {"name": "Grace", "age": 34},
    }

    first = contract.resolve([0.5, 0.5], context=first_context)[0]
    reordered = contract.resolve([0.5, 0.5], context=reordered_context)[0]
    other_agent = contract.resolve([0.5, 0.5], context=other_agent_context)[0]

    assert first == reordered
    assert first["seed"] != 42
    assert first["seed"] != other_agent["seed"]
    assert first["draw"] != other_agent["draw"]


def test_response_seed_changes_by_question_scenario_and_iteration():
    contract = ProbabilisticResponse(resolution="sample", seed=42)
    base = {
        "agent": {"name": "Ada"},
        "scenario": {"city": "Boston"},
        "question": "trust",
        "iteration": 0,
    }
    contexts = [
        base,
        {**base, "question": "confidence"},
        {**base, "scenario": {"city": "Chicago"}},
        {**base, "iteration": 1},
    ]
    seeds = {
        contract.resolve([0.5, 0.5], context=context)[0]["seed"]
        for context in contexts
    }
    assert len(seeds) == len(contexts)


def test_seed_context_strips_serialization_metadata_recursively():
    plain = ProbabilisticResponse.seed_context(
        agent={"traits": {"name": "Ada"}},
        scenario={"city": "Boston"},
        question_name="trust",
        iteration=0,
    )
    serialized = ProbabilisticResponse.seed_context(
        agent={
            "traits": {"name": "Ada", "edsl_version": "nested"},
            "edsl_version": "1.0",
            "edsl_class_name": "Agent",
        },
        scenario={
            "city": "Boston",
            "edsl_version": "1.0",
            "edsl_class_name": "Scenario",
        },
        question_name="trust",
        iteration=0,
    )
    assert plain == serialized


def test_direct_answer_invigilator_resolves_probabilities_and_keeps_audit_fields():
    question = make_question(resolution="sample", seed=42)
    agent = Agent(traits={"respondent_id": "ada"})
    agent.add_direct_question_answering_method(
        lambda self, question, scenario: {
            "probabilities": [0.1, 0.35, 0.55]
        }
    )
    scenario = Scenario({"city": "Boston"})
    survey = Survey([question])
    invigilator = InvigilatorHuman(
        agent=agent,
        question=question,
        scenario=scenario,
        model=Model("test"),
        memory_plan=MemoryPlan(survey=survey),
        current_answers={},
        survey=survey,
        iteration=0,
    )

    result = invigilator.answer_question()

    assert result.answer in question.question_options
    assert result.distribution == [0.1, 0.35, 0.55]
    assert result.resolution_method == "sample"
    assert result.resolution_seed != 42
    assert 0 <= result.resolution_draw < 1


@pytest.mark.asyncio
async def test_seeded_direct_answer_is_consistent_across_execution_engines():
    question = make_question(resolution="sample", seed=42)
    question.question_text = "How much trust in {{ city }}?"
    agent = Agent(traits={"respondent_id": "ada"})
    agent.add_direct_question_answering_method(
        lambda self, question, scenario: {
            "probabilities": [0.1, 0.35, 0.55]
        }
    )
    jobs = question.by(agent).by(Scenario({"city": "Boston"})).by(Model("test"))

    runner_results = jobs.run(disable_remote_inference=True)
    async_results = await jobs.run_async(disable_remote_inference=True)
    columns = (
        "answer.trust",
        "distribution.trust_distribution",
        "resolution_draw.trust_resolution_draw",
        "resolution_seed.trust_resolution_seed",
        "resolution_method.trust_resolution_method",
    )

    assert runner_results.select(*columns).to_list() == async_results.select(
        *columns
    ).to_list()


def test_sample_requires_seed():
    with pytest.raises(ValueError, match="explicit seed"):
        ProbabilisticResponse(resolution="sample")


@pytest.mark.parametrize(
    ("kwargs", "exception"),
    [
        ({"representation": "unknown"}, ValueError),
        ({"joint_model": "correlated"}, ValueError),
        ({"tolerance": True}, TypeError),
        ({"tolerance": "0.01"}, TypeError),
    ],
)
def test_contract_rejects_invalid_runtime_values(kwargs, exception):
    with pytest.raises(exception):
        ProbabilisticResponse(**kwargs)


@pytest.mark.parametrize("n", [True, 1.5])
def test_resolution_count_must_be_an_integer(n):
    with pytest.raises(TypeError, match="n must be an integer"):
        ProbabilisticResponse().resolve([0.5, 0.5], n=n)


def test_resolution_seed_override_must_be_an_integer():
    with pytest.raises(TypeError, match="seed must be an integer"):
        ProbabilisticResponse().resolve([0.5, 0.5], seed=True)


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
    answer, probabilities, draw, derived_seed, method = row
    assert answer in {"High", "Low"}
    assert probabilities == [0.1, 0.9]
    assert 0 <= draw < 1
    assert derived_seed != 42
    assert method == "sample"

    restored = Results.from_dict(results.to_dict())
    assert restored.select(
        "distribution.trust_distribution",
        "resolution_method.trust_resolution_method",
    ).to_list() == [([0.1, 0.9], "sample")]


def test_local_job_derives_distinct_stable_seeds_per_agent():
    question = QuestionMultipleChoice(
        question_name="trust",
        question_text="How much trust?",
        question_options=["High", "Low"],
        probabilistic_response=ProbabilisticResponse(resolution="sample", seed=42),
    )
    agents = AgentList(
        [
            Agent(traits={"respondent_id": "ada"}),
            Agent(traits={"respondent_id": "grace"}),
        ]
    )
    results = (
        question.by(agents)
        .by(Model("test", canned_response='{"probabilities":[0.5,0.5]}'))
        .run(disable_remote_inference=True)
    )
    rows = results.select(
        "agent.respondent_id", "resolution_seed.trust_resolution_seed"
    ).to_list()
    seed_by_agent = dict(rows)
    assert set(seed_by_agent) == {"ada", "grace"}
    assert len(set(seed_by_agent.values())) == 2
    assert 42 not in seed_by_agent.values()


def test_prompt_requests_probabilities_without_model_generated_randomness():
    prompt = make_question(resolution="sample", seed=42).prompt_preview().text
    assert '"probabilities" array' in prompt
    assert "Do not choose an option or generate a random draw." in prompt


def test_derived_multiple_choice_questions_remain_non_probabilistic():
    from edsl import QuestionLinearScale

    question = QuestionLinearScale(
        question_name="rating",
        question_text="Rate this.",
        question_options=[1, 2, 3, 4, 5],
    )
    assert question._validate_answer({"answer": 1})["answer"] == 1

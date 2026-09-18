import asyncio
import copy
import json
from dataclasses import replace

import httpx
import pytest

from edsl import (
    Agent,
    Cache,
    Evaluation,
    JudgmentModel,
    ProbabilisticResponse,
    QuestionFreeText,
    QuestionLinearScale,
    QuestionMultipleChoice,
    QuestionYesNo,
    Results,
    Scenario,
    ScenarioList,
    Survey,
)
from edsl.evaluations import EvaluationRunError, EvaluationValidationError


def choice(name="category", **kwargs):
    return QuestionMultipleChoice(
        question_name=name,
        question_text="Classify {{ text }}",
        question_options=["positive", "negative"],
        **kwargs,
    )


def workload(questions=None):
    return (
        Survey(questions or [choice()])
        .to_evaluation()
        .by(Scenario({"text": "hello"}))
        .by(JudgmentModel("jev-1.13.0"))
    )


def response_for(questions):
    answers = {}
    for name, q in questions.items():
        if q["type"] == "binary":
            answers[name] = {"type": "binary", "probability": 0.8}
        else:
            probabilities = {
                str(i): 1.0 if i == 1 else 0.0 for i in range(len(q["criteria"]))
            }
            answers[name] = {
                "type": q["type"],
                "probabilities": probabilities,
                "confidence": 1.0,
            }
            if q["type"] == "choice":
                answers[name]["choice"] = "1"
            else:
                answers[name].update(score=1.0, legend=dict(enumerate(q["criteria"])))
    return {
        "model": "jev-1.13.0",
        "answers": answers,
        "usage": {"input_tokens": 100, "output_tokens": 4},
    }


@pytest.fixture
def provider(monkeypatch):
    calls = []

    async def evaluate(self, state, questions, *, client):
        calls.append((copy.deepcopy(state), copy.deepcopy(questions)))
        return response_for(questions)

    monkeypatch.setattr(JudgmentModel, "async_evaluate", evaluate)
    return calls


def test_fluent_cross_product_and_snapshot(provider):
    models = [JudgmentModel("jev-1.13.0"), JudgmentModel("jev-latest")]
    scenarios = ScenarioList([Scenario({"text": "a"}), Scenario({"text": "b"})])
    survey = Survey([choice("a"), choice("b"), choice("c")])
    evaluation = (
        survey.to_evaluation()
        .by(models)
        .by(scenarios)
        .by([Agent(traits={"age": 20}), Agent(traits={"age": 30})])
    )
    plan = evaluation.compile()
    assert len(plan.batches) == 8
    assert all(len(b.questions) == 3 for b in plan.batches)
    assert provider == []
    survey.questions[0].question_text = "Changed"
    scenarios[0]["text"] = "Changed"
    assert plan.batches[0].state["scenario"]["text"] == "a"
    assert "Classify a" in plan.batches[0].questions["a"]["instructions"]
    results = plan.run(max_concurrency=2)
    assert len(results) == 8
    assert len(provider) == 8
    assert results.select("answer.a").to_list() == ["negative"] * 8
    assert results.select("model.inference_service").to_list() == ["typesafe"] * 8


def test_repeated_by_matches_jobs_semantics():
    ev = workload().by(Scenario({"extra": 1})).by(JudgmentModel("jev-latest"))
    assert dict(ev.scenarios[0]) == {"text": "hello", "extra": 1}
    assert [m.model for m in ev.models] == ["jev-latest"]
    with pytest.raises(ValueError):
        ev.by([])
    with pytest.raises(TypeError):
        ev.by(Agent(), Scenario({}))


def test_batch_splitting_and_single_request_provider():
    ev = workload([choice("a"), choice("b"), choice("c")])
    assert [
        len(b.questions) for b in ev.compile(max_questions_per_request=2).batches
    ] == [2, 1]
    ev.models[0].capabilities = replace(ev.models[0].capabilities, batching=False)
    assert len(ev.compile().batches) == 3


def test_byte_budget_splitting():
    ev = workload([choice("a"), choice("b")])
    ev.models[0].capabilities = replace(
        ev.models[0].capabilities, max_request_bytes=300
    )
    assert len(ev.compile().batches) == 2
    ev.scenarios[0]["text"] = "x" * 31_000
    with pytest.raises(EvaluationValidationError, match="context byte budget"):
        ev.compile()


def test_all_unsupported_questions_fail_before_inference(provider):
    ev = workload(
        [
            QuestionFreeText(question_name="why", question_text="Why?"),
            QuestionFreeText(question_name="how", question_text="How?"),
        ]
    )
    with pytest.raises(EvaluationValidationError) as exc:
        ev.run()
    assert "why" in str(exc.value) and "how" in str(exc.value)
    assert provider == []


@pytest.mark.parametrize(
    "feature", ["memory", "branch", "piping", "missing", "randomization"]
)
def test_reject_unsupported_semantics(feature, provider):
    ev = workload([choice("a"), choice("b")])
    if feature == "memory":
        ev.survey.set_full_memory_mode()
    elif feature == "branch":
        ev.survey.add_skip_rule("b", "True")
    elif feature == "piping":
        ev.survey.questions[1].question_text = "Given {{ a.answer }}, classify it"
    elif feature == "missing":
        ev.survey.questions[1].question_text = "Classify {{ missing }}"
    else:
        ev.survey.questions_to_randomize = ["a"]
    with pytest.raises(EvaluationValidationError):
        ev.run()
    assert provider == []


def test_score_binary_and_distributions(provider):
    scale = QuestionLinearScale(
        question_name="rating",
        question_text="Rate it",
        question_options=[1, 2, 3],
        option_labels={1: "Bad", 2: "Average", 3: "Good"},
    )
    binary = QuestionYesNo(
        question_name="yes", question_text="Is it good?", question_options=["Yes", "No"]
    )
    results = workload([scale, binary]).run()
    assert len(provider) == 1
    assert results[0].answer == {"rating": 2, "yes": "Yes"}
    assert results.select("distribution.yes_distribution").to_list()[
        0
    ] == pytest.approx([0.8, 0.2])
    assert "distribution.yes_distribution" in results.columns
    assert "distribution.yes_distribution_distribution" not in results.columns
    assert "cache_used.yes_cache_used" in results.columns
    raw = results[0]["raw_model_response"]
    assert sum(v for k, v in raw.items() if k.endswith("_input_tokens")) == 100
    assert raw["rating_raw_model_response"]["answer"]["score"] == 1


def test_scale_requires_complete_labels():
    scale = QuestionLinearScale(
        question_name="rating", question_text="Rate it", question_options=[1, 2, 3]
    )
    with pytest.raises(EvaluationValidationError, match="option_label"):
        workload([scale]).compile()


def test_sampling_cache_and_resolution_none(provider):
    q = choice(
        probabilistic_response=ProbabilisticResponse(resolution="sample", seed=42)
    )
    ev = workload([q])
    cache = Cache()
    first = ev.run(n=3, cache=cache)
    second = ev.run(n=3, cache=cache)
    assert len(provider) == 3
    assert (
        first.select("resolution_draw.*").to_list()
        == second.select("resolution_draw.*").to_list()
    )
    assert len(set(first.select("resolution_seed.*").to_list())) == 3
    assert all(second.select("cache_used.*").to_list())
    unresolved = workload(
        [choice(probabilistic_response=ProbabilisticResponse())]
    ).run()
    assert unresolved[0].answer["category"] is None
    assert unresolved.select("distribution.*").to_list() == [[0.0, 1.0]]


def test_serialization_and_packages(tmp_path, provider):
    ev = workload()
    assert Evaluation.from_dict(ev.to_dict()).to_dict() == ev.to_dict()
    ev.save(tmp_path / "evaluation.ep")
    loaded = Evaluation.load(tmp_path / "evaluation.ep")
    assert loaded.to_dict() == ev.to_dict()
    results = loaded.run()
    for include_version in (True, False):
        restored = Results.from_dict(results.to_dict(add_edsl_version=include_version))
        assert isinstance(restored[0].model, JudgmentModel)
        assert restored.select("answer.*").to_list() == ["negative"]
    results.save(tmp_path / "results.ep")
    restored = Results.load(tmp_path / "results.ep")
    assert isinstance(restored[0].model, JudgmentModel)
    assert restored.select("distribution.*").to_list() == [[0.0, 1.0]]


def test_malformed_response_is_not_cached(monkeypatch):
    async def bad(self, state, questions, *, client):
        response = response_for(questions)
        response["answers"]["category"]["probabilities"]["1"] = 0.2
        return response

    monkeypatch.setattr(JudgmentModel, "async_evaluate", bad)
    cache = Cache()
    with pytest.raises(EvaluationRunError, match="sum to 1"):
        workload().run(cache=cache)
    assert len(cache) == 0


def test_retry_incomplete_work_from_cache(monkeypatch):
    calls = []
    fail = True

    async def partial(self, state, questions, *, client):
        calls.append(list(questions))
        if "b" in questions and fail:
            raise RuntimeError("temporary failure")
        return response_for(questions)

    monkeypatch.setattr(JudgmentModel, "async_evaluate", partial)
    ev = workload([choice("a"), choice("b")])
    cache = Cache()
    with pytest.raises(EvaluationRunError) as exc:
        ev.run(cache=cache, max_questions_per_request=1)
    assert len(exc.value.partial_results) == 0
    assert len(cache) == 1
    fail = False
    assert len(ev.run(cache=cache, max_questions_per_request=1)) == 1
    assert calls.count(["a"]) == 1
    assert calls.count(["b"]) == 2


def test_transport_noul_and_retry(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-credential")
    attempts = []

    def handle(request):
        attempts.append(json.loads(request.content))
        if len(attempts) == 1:
            return httpx.Response(429, headers={"retry-after": "0"})
        return httpx.Response(
            200,
            json={
                "model": "jev-1.13.0",
                "answers": {"q": {"type": "noul", "noul": 0.8}},
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            return await JudgmentModel().async_evaluate(
                {}, {"q": {"type": "binary", "instructions": "Yes?"}}, client=client
            )

    result = asyncio.run(run())
    assert attempts[0]["questions"]["q"]["type"] == "noul"
    assert result["answers"]["q"] == {"type": "binary", "probability": 0.8}
    assert "test-credential" not in json.dumps(JudgmentModel().to_dict())


def test_async_and_bounded_concurrency(monkeypatch):
    active = maximum = 0

    async def evaluate(self, state, questions, *, client):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0.001)
        active -= 1
        return response_for(questions)

    monkeypatch.setattr(JudgmentModel, "async_evaluate", evaluate)
    ev = workload([choice(str_name) for str_name in ("a", "b", "c", "d")])

    async def run():
        with pytest.raises(RuntimeError, match="event loop"):
            ev.run()
        return await ev.run_async(max_questions_per_request=1, max_concurrency=2)

    assert len(asyncio.run(run())) == 1
    assert maximum == 2


def test_survey_instructions_and_dynamic_options(provider):
    from edsl import Instruction

    q = QuestionMultipleChoice(
        question_name="q",
        question_text="Classify {{ scenario.text }} for {{ agent.age }}",
        question_options="{{ choices }}",
    )
    ev = (
        Survey([Instruction(name="rubric", text="Use {{ policy }}"), q])
        .to_evaluation()
        .by(Scenario({"text": "hello", "policy": "the rubric", "choices": ["A", "B"]}))
        .by(Agent(traits={"age": 40}))
        .by(JudgmentModel())
    )
    results = ev.run()
    assert "Use the rubric" in provider[0][1]["q"]["instructions"]
    assert "for 40" in provider[0][1]["q"]["instructions"]
    assert results[0].answer["q"] == "B"
    assert results[0]["question_to_attributes"]["q"]["question_options"] == ["A", "B"]


def test_capabilities_and_indices(provider):
    ev = workload([QuestionYesNo(question_name="yes", question_text="Yes?")])
    ev.models[0].capabilities = replace(
        ev.models[0].capabilities, primitives=frozenset({"choice"})
    )
    with pytest.raises(EvaluationValidationError, match="binary"):
        ev.compile()
    ev = workload().by([JudgmentModel("one"), JudgmentModel("two")])
    results = ev.run(n=2)
    assert [r.indices for r in results] == [
        {"agent": 0, "scenario": 0, "model": 0},
        {"agent": 0, "scenario": 0, "model": 0},
        {"agent": 0, "scenario": 0, "model": 1},
        {"agent": 0, "scenario": 0, "model": 1},
    ]


@pytest.mark.parametrize(
    "mutation", ["missing", "extra", "type", "nan", "confidence", "choice"]
)
def test_provider_contract_validation(monkeypatch, mutation):
    async def evaluate(self, state, questions, *, client):
        response = response_for(questions)
        answer = response["answers"]["category"]
        if mutation == "missing":
            response["answers"].clear()
        elif mutation == "extra":
            response["answers"]["extra"] = answer
        elif mutation == "type":
            answer["type"] = "binary"
        elif mutation == "nan":
            answer["probabilities"]["1"] = float("nan")
        elif mutation == "confidence":
            answer["confidence"] = 2
        else:
            answer["choice"] = "0"
        return response

    monkeypatch.setattr(JudgmentModel, "async_evaluate", evaluate)
    cache = Cache()
    with pytest.raises(EvaluationRunError):
        workload().run(cache=cache)
    assert len(cache) == 0


def test_transport_auth_failure_does_not_retry_or_expose_body(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "private-key")
    attempts = []

    def handle(request):
        attempts.append(request)
        return httpx.Response(401, text="private-key")

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            await JudgmentModel().async_evaluate({}, {}, client=client)

    with pytest.raises(RuntimeError, match="HTTP 401") as exc:
        asyncio.run(run())
    assert "private-key" not in str(exc.value)
    assert len(attempts) == 1


def test_generic_provider_round_trip(monkeypatch):
    class LocalJudgment(JudgmentModel):
        async def async_evaluate(self, state, questions, *, client):
            return response_for(questions)

    monkeypatch.setattr(JudgmentModel, "_providers", {})
    JudgmentModel.register("local_judgment", LocalJudgment)
    model = JudgmentModel("example", service_name="local_judgment")
    assert isinstance(model, LocalJudgment)
    ev = workload().by(model)
    restored = Evaluation.from_dict(ev.to_dict())
    assert isinstance(restored.models[0], LocalJudgment)
    assert restored.run().select("answer.*").to_list() == ["negative"]


def test_model_list_round_trip(tmp_path, provider):
    from edsl import ModelList, Model

    models = ModelList([JudgmentModel("jev-1.13.0")])
    results = workload().by(models).run()
    restored = ModelList.from_jsonl(results.models.to_jsonl())
    assert isinstance(restored[0], JudgmentModel)
    models.save(tmp_path / "models.ep")
    assert isinstance(ModelList.load(tmp_path / "models.ep")[0], JudgmentModel)
    ordinary = ModelList.from_dict(ModelList([Model("test")]).to_dict())
    assert ordinary[0].model == "test"


def test_persisted_cache_replays_without_inference(tmp_path, provider, monkeypatch):
    ev = workload([choice("a"), choice("b")])
    results = ev.run()
    results.cache.save(tmp_path / "cache.json.gz")
    ev.save(tmp_path / "evaluation.ep")

    async def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected inference")

    monkeypatch.setattr(JudgmentModel, "async_evaluate", forbidden)
    restored = Evaluation.load(tmp_path / "evaluation.ep")
    replay = restored.run(cache=Cache.load(tmp_path / "cache.json.gz"))
    assert replay[0].answer == results[0].answer
    assert all(replay[0]["cache_used_dict"].values())


def test_independently_rounded_provider_score(monkeypatch):
    # Observed in Jev 1.13.0: the returned score is 0.01 while the returned
    # distribution is [1, 0, 0]. Preserve both; do not discard the whole batch.
    async def evaluate(self, state, questions, *, client):
        return {
            "model": "jev-1.13.0",
            "answers": {
                "rating": {
                    "type": "score",
                    "score": 0.01,
                    "confidence": 1.0,
                    "probabilities": {"0": 1.0, "1": 0.0, "2": 0.0},
                }
            },
            "usage": {"input_tokens": 100, "output_tokens": 20},
        }

    monkeypatch.setattr(JudgmentModel, "async_evaluate", evaluate)
    q = QuestionLinearScale(
        question_name="rating",
        question_text="Rate it",
        question_options=[1, 2, 3],
        option_labels={1: "Low", 2: "Medium", 3: "High"},
    )
    results = workload([q]).run()
    assert results[0].answer["rating"] == 1
    raw = results[0]["raw_model_response"]["rating_raw_model_response"]
    assert raw["answer"]["score"] == 0.01
    assert raw["score_from_distribution"] == 0
    assert raw["score_difference"] == 0.01


@pytest.mark.parametrize(
    "probabilities,adjusted",
    [
        ({"0": 0.61, "1": 0.38}, True),
        ({"0": 0.62, "1": 0.39}, True),
        ({"0": 0.6, "1": 0.4}, False),
        ({"0": 0.6, "1": 0.3}, False),
        ({"0": -0.01, "1": 1.0}, False),
    ],
)
def test_typesafe_bounded_probability_rounding(monkeypatch, probabilities, adjusted):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test-key")

    def handle(request):
        return httpx.Response(
            200,
            json={
                "model": "jev-1.13.0",
                "answers": {
                    "q": {
                        "type": "choice",
                        "choice": "0",
                        "confidence": 0.8,
                        "probabilities": probabilities,
                    }
                },
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handle)) as client:
            return await JudgmentModel().async_evaluate(
                {}, {"q": {"type": "choice"}}, client=client
            )

    answer = asyncio.run(run())["answers"]["q"]
    if adjusted:
        assert sum(answer["probabilities"].values()) == pytest.approx(1)
        assert answer["reported_probabilities"] == probabilities
        assert answer["probability_normalization"]["reported_total"] == pytest.approx(
            sum(probabilities.values())
        )
    else:
        assert answer["probabilities"] == probabilities
        assert "reported_probabilities" not in answer

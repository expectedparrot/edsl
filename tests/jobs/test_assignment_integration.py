"""Assignment schedules survive persistence, component edits, and execution."""

import asyncio
from unittest.mock import Mock

import pytest

from edsl import Agent, Cache, Jobs, Model, Scenario, Survey
from edsl.jobs.exceptions import JobsRunError, JobsValueError
from edsl.questions import QuestionFreeText
from edsl.runner.models import JobState
from edsl.runner.serialization import deserialize_job, serialize_job
from edsl.runner.service import JobService
from edsl.runner.storage import InMemoryStorage


@pytest.fixture
def assignment_job():
    return Jobs(
        survey=Survey(
            [QuestionFreeText(question_name="q", question_text="Topic: {{ topic }}")]
        ),
        agents=[Agent(traits={"person": i}) for i in range(2)],
        scenarios=[Scenario({"topic": i}) for i in range(2)],
        models=[Model("test", canned_response="ok")],
    )


def row_indices(rows):
    return [dict(zip(("agent", "scenario", "model"), row)) for row in rows]


@pytest.mark.parametrize("mode", ["explicit", "zip", "filtered", "empty", "cross"])
@pytest.mark.parametrize("transport", ["dict", "jsonl", "ep", "runner"])
def test_assignment_round_trip(assignment_job, tmp_path, mode, transport):
    job = assignment_job
    if mode == "explicit":
        job.assign([(1, 1, 0), (0, 0, 0), (1, 1, 0)])
    elif mode == "zip":
        job.zip_assign()
    elif mode == "filtered":
        job.include_when("{{ agent.person == scenario.topic }}")
    elif mode == "empty":
        job.assign([])
    expected = list(job.assignment_plan.iter_indices())
    if transport == "dict":
        restored = Jobs.from_dict(job.to_dict())
    elif transport == "jsonl":
        restored = Jobs.from_jsonl(job.to_jsonl())
    elif transport == "ep":
        path = tmp_path / "job.ep"
        job.save(path)
        restored = Jobs.load(path)
    else:
        restored = deserialize_job(serialize_job(job))
    assert len(restored) == len(expected)
    assert list(restored.assignment_plan.iter_indices()) == expected
    assert restored.assignment_plan.mode == job.assignment_plan.mode
    assert restored._include_expression == job._include_expression
    service = JobService(InMemoryStorage())
    job_id, _, data = service.submit_job(restored, n=2)
    definitions = list(data["interview_defs"].values())
    assert [d["indices"] for d in definitions] == [
        d for d in row_indices(expected) for _ in range(2)
    ]
    assert [d["iteration"] for d in definitions] == [
        i for _ in expected for i in range(2)
    ]
    if not expected:
        assert service.jobs.get_state(job_id) == JobState.COMPLETED
        assert len(service.build_edsl_results(job_id)) == 0


@pytest.mark.parametrize("transport", ["dict", "jsonl", "ep", "runner"])
def test_filter_serialization_resolves_implicit_defaults(tmp_path, transport):
    job = Jobs(
        survey=Survey([QuestionFreeText(question_name="q", question_text="Hello")])
    )
    job.include_when("{{ True }}")
    if transport == "dict":
        restored = Jobs.from_dict(job.to_dict())
    elif transport == "jsonl":
        restored = Jobs.from_jsonl(job.to_jsonl())
    elif transport == "ep":
        job.save(tmp_path / "default.ep")
        restored = Jobs.load(tmp_path / "default.ep")
    else:
        restored = deserialize_job(serialize_job(job))
    assert list(restored.assignment_plan.iter_indices()) == [(0, 0, 0)]


@pytest.mark.parametrize("axis", ["agents", "scenarios", "models"])
def test_same_length_replacement_preserves_plan(assignment_job, axis):
    job = assignment_job.zip_assign()
    expected = list(job.assignment_plan.iter_indices())
    setattr(job, axis, getattr(job, axis))
    assert list(job.assignment_plan.iter_indices()) == expected
    if axis == "models":
        with pytest.warns(UserWarning, match="replacing"):
            job.by(Model("test", canned_response="new"))
        assert list(job.assignment_plan.iter_indices()) == expected


@pytest.mark.parametrize("axis", ["agents", "scenarios", "models"])
def test_length_change_fails_before_mutating_job(assignment_job, axis):
    job = assignment_job.zip_assign()
    original = getattr(job, axis)
    with pytest.raises(JobsValueError, match=f"number of {axis}"):
        setattr(job, axis, list(original) + [original[0]])
    assert getattr(job, axis) is original
    assert len(job) == 2


def test_filter_is_recomputed_after_component_replacement(assignment_job):
    job = assignment_job.include_when("{{ agent.person == scenario.topic }}")
    assert len(job) == 2
    job.scenarios = [Scenario({"topic": 0})]
    assert list(job.assignment_plan.iter_indices()) == [(0, 0, 0)]


def test_cartesian_plan_remains_reusable(assignment_job):
    plan = assignment_job.assignment_plan
    expected = list(plan.iter_indices())
    plan.validate(
        assignment_job.agents, assignment_job.scenarios, assignment_job.models
    )
    assert len(expected) == len(plan) == 4
    assert list(plan.iter_indices()) == expected
    assert plan.to_dict()["assignments"] == row_indices(expected)


@pytest.mark.parametrize("rows", [[(1, 1, 0), (0, 0, 0), (1, 1, 0)], []])
def test_run_preserves_rows_duplicates_and_iterations(
    assignment_job, rows, tmp_path, monkeypatch
):
    from edsl.object_store.store import ObjectStore

    monkeypatch.setattr(
        ObjectStore, "default_root", staticmethod(lambda: tmp_path / "objects")
    )
    job = assignment_job.assign(rows)
    results = job.run(
        n=2,
        cache=Cache(),
        disable_remote_inference=True,
        disable_remote_cache=True,
        check_api_keys=False,
        max_concurrency=2,
    )
    assert [r.indices for r in results] == [
        d for d in row_indices(rows) for _ in range(2)
    ]
    assert [r["iteration"] for r in results] == [i for _ in rows for i in range(2)]
    assert [r.answer["q"] for r in results] == ["ok"] * (len(rows) * 2)


@pytest.mark.parametrize("async_run", [False, True])
def test_invalid_remote_results_never_execute_locally(
    assignment_job, monkeypatch, async_run
):
    handler = Mock()
    handler.use_remote_inference.return_value = True
    handler.poll_remote_inference_job.return_value = (object(), None)
    monkeypatch.setattr(
        assignment_job, "_create_remote_inference_handler", lambda: handler
    )
    monkeypatch.setattr(
        assignment_job, "_start_remote_inference_job", lambda _: object()
    )
    monkeypatch.setattr(assignment_job, "_remote_results_are_invalid", lambda _: True)
    local_runner = Mock(side_effect=AssertionError("Unexpected local execution"))
    local_async_runner = Mock(side_effect=AssertionError("Unexpected local execution"))
    monkeypatch.setattr(assignment_job, "_execute_with_runner", local_runner)
    monkeypatch.setattr(
        assignment_job, "_execute_with_remote_cache", local_async_runner
    )
    with pytest.raises(JobsRunError, match="structurally invalid"):
        if async_run:
            asyncio.run(assignment_job.run_async(cache=False, offload_execution=True))
        else:
            assignment_job.run(cache=False, offload_execution=True)
    local_runner.assert_not_called()
    local_async_runner.assert_not_called()
    handler.poll_remote_inference_job.assert_called_once()


def test_sparse_submission_does_not_expand_cross_product(assignment_job, monkeypatch):
    job = assignment_job.assign([(1, 1, 0)])
    monkeypatch.setattr(
        "edsl.jobs.assignment_plan.product",
        Mock(side_effect=AssertionError("Unexpected Cartesian expansion")),
    )
    service = JobService(InMemoryStorage())
    _, _, data = service.submit_job(job)
    assert len(data["interview_defs"]) == 1


def test_prompts_and_costs_follow_assignment_rows(assignment_job, monkeypatch):
    from edsl.jobs.cost_estimation.job_cost_estimator import JobCostEstimator
    from edsl.jobs.jobs_pricing_estimation import JobsPrompts

    prices = {
        ("test", "test"): {
            token_type: {
                "one_usd_buys": 1000,
                "service_stated_token_qty": 1000,
                "service_stated_token_price": 1,
            }
            for token_type in ("input", "output")
        }
    }
    monkeypatch.setattr(JobsPrompts, "price_lookup", property(lambda self: prices))
    rows = [(1, 1, 0), (0, 0, 0), (1, 1, 0)]
    job = assignment_job.assign(rows)
    prompt_rows = job.prompts().to_scenario_list()
    estimate = JobCostEstimator().estimate_cost(job, price_lookup=prices)
    for actual in (prompt_rows, estimate._rows):
        assert [(r["agent_index"], r["scenario_index"]) for r in actual] == [
            (a, s) for a, s, _ in rows
        ]


def test_dependency_package_preserves_assignment_plan(assignment_job, tmp_path):
    dependency = assignment_job.assign([(1, 1, 0), (0, 0, 0)])
    job = Jobs(survey=dependency.survey, models=[Model("test")])
    job._depends_on = dependency
    job.save(tmp_path / "dependency.ep")
    restored = Jobs.load(tmp_path / "dependency.ep")
    assert list(restored._depends_on.assignment_plan.iter_indices()) == [
        (1, 1, 0),
        (0, 0, 0),
    ]

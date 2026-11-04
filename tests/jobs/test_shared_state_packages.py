"""Saved inputs must retain the state program and its execution schedule."""

import pytest

from edsl import Jobs, Model, Results, Survey
from examples.shared_state_acceptance import build_case, check_case


@pytest.fixture(autouse=True)
def isolate_object_store(tmp_path, monkeypatch):
    from edsl.object_store.store import ObjectStore

    monkeypatch.setattr(
        ObjectStore, "default_root", staticmethod(lambda: tmp_path / "objects")
    )


@pytest.mark.parametrize("name", ["activity_poll", "posted_price_market"])
def test_packaged_job_executes_original_state_program(tmp_path, name):
    _, job, _ = build_case(name)
    path = tmp_path / "jobs.ep"
    job.save(str(path))
    restored = Jobs.load(str(path))
    assert restored.to_dict() == job.to_dict()

    results = restored.run(
        disable_remote_inference=True,
        disable_remote_cache=True,
        check_api_keys=False,
        cache=False,
        progress_bar=False,
    )
    check_case(name, results)
    result_path = tmp_path / "results.ep"
    results.save(str(result_path))
    reloaded = Results.load(str(result_path))
    assert reloaded.shared_state == results.shared_state
    assert reloaded.survey.to_dict() == results.survey.to_dict()
    check_case(name, reloaded)


def test_package_preserves_snapshot_round_schedule(tmp_path):
    from examples.shared_state_advanced_acceptance import build_case as advanced_case

    job = advanced_case("repeated_matrix", Model("test"))
    path = tmp_path / "rounds.ep"
    job.save(str(path))
    assert Jobs.load(str(path)).to_dict() == job.to_dict()


@pytest.mark.parametrize("format", ["ep", "jsonl"])
def test_survey_round_trip_preserves_state_steps(tmp_path, format):
    job, _, _ = build_case("activity_poll")
    survey = job.survey
    if format == "ep":
        path = tmp_path / "survey.ep"
        survey.save(str(path))
        restored = Survey.load(str(path))
    else:
        restored = Survey.from_jsonl(survey.to_jsonl())
    assert restored.to_dict() == survey.to_dict()


@pytest.mark.parametrize("async_run", [False, True])
@pytest.mark.parametrize("override", [False, True])
def test_run_preserves_saved_schedule_unless_overridden(
    monkeypatch, async_run, override
):
    import asyncio

    job, _, schedule = build_case("activity_poll")
    expected = "concurrent" if override else schedule
    captured = []

    def intercept(self, config):
        captured.append(config.parameters.interview_schedule)
        # Stop before credentials, remote submission, or local model execution.
        raise RuntimeError("captured run config")

    monkeypatch.setattr(Jobs, "_run", intercept)
    kwargs = {"interview_schedule": "concurrent"} if override else {}
    with pytest.raises(RuntimeError, match="captured run config"):
        if async_run:
            asyncio.run(job.run_async(**kwargs))
        else:
            job.run(**kwargs)
    assert captured == [expected]


@pytest.mark.parametrize("override", [False, True])
def test_batch_split_rejects_shared_state_before_execution(monkeypatch, override):
    from edsl.jobs.exceptions import JobsValueError

    job, _, _ = build_case("activity_poll")
    monkeypatch.setattr(
        job, "generate_interviews", lambda: pytest.fail("must not split")
    )
    monkeypatch.setattr(job, "run", lambda **kwargs: pytest.fail("must not execute"))
    kwargs = {"interview_schedule": "concurrent"} if override else {}
    with pytest.raises(
        JobsValueError, match="cannot split shared-state or ordered jobs"
    ):
        job.run_batch(num_batches=2, **kwargs)


@pytest.mark.parametrize("explicit", [False, True])
def test_batch_split_rejects_stateless_ordered_schedule(monkeypatch, explicit):
    from edsl.jobs.exceptions import JobsValueError

    job = Jobs.example()
    if not explicit:
        job.run_config.parameters.interview_schedule = "serial"
    monkeypatch.setattr(
        job, "generate_interviews", lambda: pytest.fail("must not split")
    )
    kwargs = {"interview_schedule": "serial"} if explicit else {}
    with pytest.raises(
        JobsValueError, match="cannot split shared-state or ordered jobs"
    ):
        job.run_batch(num_batches=2, **kwargs)


def test_single_batch_runs_complete_shared_state_job():
    _, job, _ = build_case("posted_price_market")
    results = job.run_batch(
        num_batches=1,
        disable_remote_inference=True,
        disable_remote_cache=True,
        check_api_keys=False,
        cache=False,
        progress_bar=False,
    )
    check_case("posted_price_market", results)

"""Saved inputs must retain the state program and its execution schedule."""

import pytest

from edsl import Jobs, Model, Results, Survey
from edsl.runner import Runner
from examples.shared_state_acceptance import build_case, check_case


@pytest.mark.parametrize("name", ["activity_poll", "posted_price_market"])
def test_packaged_job_executes_original_state_program(tmp_path, name):
    _, job, _ = build_case(name)
    path = tmp_path / "jobs.ep"
    job.save(str(path))
    restored = Jobs.load(str(path))
    assert restored.to_dict() == job.to_dict()

    results = (
        Runner(interview_schedule=restored.run_config.parameters.interview_schedule)
        .submit(restored, cache=False)
        .results()
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

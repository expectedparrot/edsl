"""Verify saved instruments independently of matching response counts and column names."""

import json

from click.testing import CliRunner

from edsl import Model, QuestionFreeText, Results, Survey
from edsl.__main__ import app


def test_check_recorded_survey_and_inspect_each_source(tmp_path):
    expected = Survey(
        [QuestionFreeText(question_name="feedback", question_text="Rate reliability.")]
    )
    recorded = Survey(
        [QuestionFreeText(question_name="feedback", question_text="Rate fares.")]
    )
    results_file, job_file = tmp_path / "answers.ep", tmp_path / "job.ep"
    Results(survey=recorded, data=[]).git.save(results_file, sync_coop=False)
    expected.by(Model("test")).git.save(job_file, sync_coop=False)
    runner = CliRunner()
    check = ["results", "check-survey", str(results_file), "--against", str(job_file)]
    mismatch = runner.invoke(app, check)
    assert mismatch.exit_code == 5, mismatch.output
    err = json.loads(mismatch.output)["error"]
    assert err["code"] == "SURVEY_MISMATCH"
    assert err["details"][0]["results_path"] == str(results_file)
    assert err["details"][0]["survey_matches"] is False
    assert err["details"][0]["changed_questions"] == [
        {
            "question": "feedback",
            "differences": {
                "question_text": {
                    "expected": "Rate reliability.",
                    "recorded": "Rate fares.",
                }
            },
        }
    ]
    for path, kind, wording in [
        (job_file, "Jobs", "Rate reliability."),
        (results_file, "Results", "Rate fares."),
    ]:
        result = runner.invoke(app, ["surveys", "questions", str(path)])
        assert result.exit_code == 0, result.output
        info = json.loads(result.output)["data"]
        assert info["source_object_type"] == kind
        assert info["questions"][0]["question_text"] == wording
        inspected = runner.invoke(app, ["inspect", str(path)])
        assert (
            json.loads(inspected.output)["data"]["stored_survey"]["sample_questions"][
                0
            ]["question_text"]
            == wording
        )
        assert (
            wording in runner.invoke(app, ["inspect", str(path), "--markdown"]).output
        )
    expected_file = tmp_path / "recorded.json"
    expected_file.write_text(json.dumps(recorded.to_dict()))
    same = runner.invoke(app, [*check[:-1], str(expected_file)])
    assert same.exit_code == 0, same.output
    assert json.loads(same.output)["data"]["survey_matches"]


def test_routing_differences_survive_question_match():
    from edsl.cli_commands.results import _survey_differences

    original = Survey.example()
    changed = Survey.from_dict(original.to_dict())
    changed.add_stop_rule("q0", "{{ q0.answer }} == 'no'")
    delta = _survey_differences(original, changed)
    assert delta["different_survey_fields"] == ["rule_collection"]
    assert delta["changed_questions"] == []


def test_pydantic_required_property_order_across_package_formats(tmp_path):
    from edsl.questions.question_pydantic import QuestionPydantic

    survey = Survey([QuestionPydantic.example()])
    job_path, results_path = tmp_path / "job.ep", tmp_path / "results.ep"
    survey.by(Model("test")).git.save(job_path, sync_coop=False)
    Results(survey=survey, data=[]).git.save(results_path, sync_coop=False)
    check = CliRunner().invoke(
        app, ["results", "check-survey", str(results_path), "--against", str(job_path)]
    )
    assert check.exit_code == 0, check.output

import json

from click.testing import CliRunner
import pytest

from edsl import JudgmentModel, QuestionMultipleChoice, Scenario, Survey
from edsl.__main__ import app


@pytest.mark.parametrize("ext", ["ep", "json"])
def test_compiles_actual_evaluation_without_returning_scenario_values(tmp_path, ext):
    survey = Survey(
        [
            QuestionMultipleChoice(
                question_name="choice",
                question_text="Classify {{ text }}.",
                question_options=["A", "B"],
            )
        ]
    )
    ev = (
        survey.to_evaluation()
        .by(Scenario({"text": "PRIVATE CONTENT", "human_key": "PRIVATE ANSWER"}))
        .by(JudgmentModel())
    )
    path = tmp_path / ("review." + ext)
    if ext == "ep":
        ev.git.save(path, sync_coop=False)
    else:
        path.write_text(json.dumps(ev.to_dict()))
    runner = CliRunner()
    inspection = runner.invoke(app, ["inspect", str(path)])
    assert (
        inspection.exit_code == 0
        and json.loads(inspection.output)["data"]["object_type"] == "Evaluation"
    )
    check = ["validate", "--file", str(path)]
    response = runner.invoke(app, check)
    assert response.exit_code == 0, response.output
    data = json.loads(response.output)["data"]
    assert (
        data["object_type"],
        data["result_count"],
        data["request_count"],
        data["judgment_count"],
    ) == ("evaluation", 1, 1, 1)
    assert data["scenario_fields"] == ["human_key", "text"]
    assert "PRIVATE" not in response.output
    failure = runner.invoke(
        app, check + ["--type", "evaluation", "--allow-scenario-field", "text"]
    )
    assert failure.exit_code == 5
    issue = json.loads(failure.output)["error"]
    assert issue["code"] == "EVALUATION_CONTEXT_MISMATCH"
    assert issue["details"] == [{"unexpected_fields": ["human_key"]}]
    assert "PRIVATE" not in failure.output
    ok = runner.invoke(
        app,
        check
        + ["--allow-scenario-field", "human_key", "--allow-scenario-field", "text"],
    )
    assert ok.exit_code == 0


def test_survey_is_not_an_evaluation(tmp_path):
    survey = Survey(
        [
            QuestionMultipleChoice(
                question_name="q", question_text="Choose.", question_options=["A", "B"]
            )
        ]
    )
    path = tmp_path / "review.ep"
    survey.git.save(path)
    response = CliRunner().invoke(
        app, ["validate", "--file", str(path), "--type", "evaluation"]
    )
    assert response.exit_code == 5
    assert (
        "Expected Evaluation, found Survey"
        in json.loads(response.output)["error"]["message"]
    )

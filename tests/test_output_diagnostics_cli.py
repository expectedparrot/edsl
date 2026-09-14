import json

from click.testing import CliRunner

from edsl import Agent, Model, QuestionFreeText, Results, Scenario, Survey
from edsl.__main__ import app
from edsl.inference_services.services.deep_infra_service import DeepInfraService
from edsl.results import Result


def test_inspect_warns_and_shows_effective_output_limit(tmp_path):
    model = DeepInfraService.create_model("deepseek-ai/DeepSeek-R1")(
        max_tokens=1000, skip_api_key_check=True
    )
    job = QuestionFreeText(question_name="q", question_text="Hi").by(model)
    path = tmp_path / "job.json"
    path.write_text(json.dumps(job.to_dict()))
    result = CliRunner().invoke(app, ["inspect", str(path)])
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["status"] == "ok"
    assert envelope["data"]["output_token_policies"][0]["effective_max_tokens"] == 1000
    assert any(
        warning["code"] == "LOW_REASONING_OUTPUT_LIMIT"
        for warning in envelope["warnings"]
    )


def test_results_summary_does_not_count_placeholder_as_an_answer(tmp_path):
    survey = Survey([QuestionFreeText(question_name="q", question_text="Hi")])
    row = Result(
        agent=Agent(),
        scenario=Scenario(),
        model=Model("test"),
        iteration=0,
        answer={"q": None},
    )
    results = Results(survey=survey, data=[row], total_results=1)
    path = tmp_path / "results.json"
    path.write_text(json.dumps(results.to_dict()))
    output = CliRunner().invoke(app, ["results", "summary", str(path)])
    assert output.exit_code == 0, output.output
    envelope = json.loads(output.output)
    assert envelope["status"] == "ok"
    assert envelope["data"]["result_count"] == 1
    summary = envelope["data"]["completion"]
    assert summary["answers_produced"] == summary["answers_validated"] == 0
    assert summary["planned_interview_rows"] == summary["placeholder_rows"] == 1

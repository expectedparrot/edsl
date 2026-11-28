"""The JSON envelope describes unused scenario columns without exposing their values."""

import json

from click.testing import CliRunner
import pytest

from edsl import (
    Instruction,
    Jobs,
    Model,
    QuestionFreeText,
    Scenario,
    ScenarioList,
    Survey,
)
from edsl.__main__ import app
from edsl.cli_commands.jobs import scenario_field_warnings


def command(*args):
    result = CliRunner().invoke(app, list(map(str, args)))
    assert result.exit_code == 0, (result.output, result.exception)
    envelope = json.loads(result.output)
    assert envelope["status"] == "ok"
    return envelope


def test_json_after_build_edit_and_run(tmp_path):
    survey_path, scenario_path, model_path, job_path, result_path = [
        tmp_path / (name + ".ep")
        for name in ("survey", "rows", "models", "job", "results")
    ]
    from edsl import ModelList

    survey = Survey(
        [QuestionFreeText(question_name="q", question_text="Describe {{ name }}.")]
    )
    survey.git.save(survey_path)
    scenarios = ScenarioList(
        [
            Scenario(
                {"name": "A", "record_id": "secret-id", "preference": "secret-trait"}
            )
        ]
    )
    scenarios.git.save(scenario_path)
    ModelList([Model("test")]).git.save(model_path)
    build = command(
        "jobs",
        "build",
        "--survey",
        survey_path,
        "--scenarios",
        scenario_path,
        "--models",
        model_path,
        "--output",
        job_path,
    )
    (warning,) = build["warnings"]
    assert warning["code"] == "UNREFERENCED_SCENARIO_FIELDS"
    assert warning["fields"] == ["preference", "record_id"]
    assert "secret" not in json.dumps(warning)
    assert Jobs.git.load(job_path, sync_coop=False).scenarios == scenarios
    for response in (
        command("jobs", "edit", job_path, "--scenarios", scenario_path),
        command("run", job_path, "--local", "--output", result_path),
        command(
            "run",
            "--survey",
            survey_path,
            "--scenario_list",
            scenario_path,
            "--model",
            "test",
            "--local",
            "--output",
            tmp_path / "components-results.ep",
        ),
    ):
        assert warning in response["warnings"]


@pytest.mark.parametrize(
    "template",
    [
        "{{ scenario.price }}",
        "{{ scenario['price'] }}",
        "{{ scenario.get('price') }}",
        "{{ price }}",
    ],
)
def test_recognizes_static_paths_and_instruction(template):
    q = QuestionFreeText(question_name="q", question_text=template)
    job = Jobs(
        survey=Survey([Instruction("direction", "Remember {{ currency }}."), q])
    ).by(Scenario({"price": 3, "currency": "USD", "row": 1}))
    assert scenario_field_warnings(job)[0]["fields"] == ["row"]


@pytest.mark.parametrize(
    "template", ["{{ scenario }}", "{{ scenario[chosen] }}", "{{ scenario.items() }}"]
)
def test_dynamic_access_is_inconclusive(template):
    job = Jobs(
        survey=Survey([QuestionFreeText(question_name="q", question_text=template)])
    ).by(Scenario({"price": 3, "currency": "USD", "chosen": "price"}))
    assert scenario_field_warnings(job) == []


def test_no_warning_when_all_fields_are_read():
    survey = Survey(
        [
            QuestionFreeText(
                question_name="q", question_text="{{ price }} {{ currency }}"
            )
        ]
    )
    assert (
        scenario_field_warnings(
            Jobs(survey=survey).by(Scenario({"price": 3, "currency": "USD"}))
        )
        == []
    )
    assert scenario_field_warnings(Jobs(survey=survey)) == []

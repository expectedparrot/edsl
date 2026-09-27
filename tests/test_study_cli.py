import csv
import json
import shlex
import subprocess
import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from edsl.__main__ import app


def payload(result):
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_study_start_allocates_next_path_and_creates_empty_directory(tmp_path):
    first = payload(CliRunner().invoke(app, ["study", "start", "--root", str(tmp_path), "--topic", "Cognitive Survey"]))
    assert first["data"]["recommended_study"] == "sessions/topic_cognitive-survey/study_a"
    assert (tmp_path / "sessions/topic_cognitive-survey/study_a").is_dir()
    root = Path(first["data"]["study_root"])
    assert first["data"]["created"] is True
    assert list(root.iterdir()) == []
    assert shlex.split(first["data"]["next_action"]) == ["ep", "study", "scaffold", str(root)]

    second = payload(CliRunner().invoke(app, ["study", "start", "--root", str(tmp_path), "--topic", "Cognitive Survey"]))
    assert second["data"]["recommended_study"] == "sessions/topic_cognitive-survey/study_b"


def test_study_start_no_create_is_read_only_and_routes_back_to_allocation(tmp_path):
    root = tmp_path / "workspace with spaces"
    result = payload(CliRunner().invoke(app, [
        "study", "start", "--root", str(root), "--topic", "Researcher's topic",
        "--summary-limit", "2", "--no-create",
    ]))["data"]

    assert result["created"] is False
    assert not root.exists()
    assert "plan.md" not in result["next_action"]
    assert "continue an existing study" in result["next_action"]
    assert shlex.join([
        "ep", "study", "start", "--root", str(root), "--topic", "Researcher's topic",
        "--summary-limit", "2", "--create",
    ]) in result["next_action"]


def test_study_start_help_distinguishes_directory_from_scaffold():
    result = CliRunner().invoke(app, ["study", "start", "--help"])
    assert result.exit_code == 0
    assert "empty directory" in result.output
    assert "create its neutral scaffold" not in result.output


@pytest.mark.parametrize("study_type", ["edsl", "simulation"])
def test_neutral_scaffold_hands_off_to_plan_without_method_state(tmp_path, study_type):
    root = tmp_path / "study"
    data = payload(CliRunner().invoke(app, [
        "study", "scaffold", str(root), "--type", study_type,
    ]))["data"]

    for relative in ("Makefile", "analysis/plot_style.py", "writeup/report.css"):
        assert (root / relative).is_file()
    for relative in ("plan.md", "workflow-gates.json", "edsl_jobs/job_a/study_survey.py"):
        assert not (root / relative).exists()
    assert data["template"] is None
    assert data["next_edits"] == []
    assert data["phase_commands"] == {}
    assert data["next_action"] == (
        "Create plan.md with the Write tool and obtain approval before method-specific scaffolding."
    )


def test_study_lifecycle_follows_start_handoff_and_preserves_approved_plan(tmp_path):
    runner = CliRunner()
    workspace = tmp_path / "researcher's workspace"
    start = payload(runner.invoke(app, [
        "study", "start", "--root", str(workspace), "--topic", "Lifecycle",
    ]))["data"]
    root = Path(start["study_root"])
    command = shlex.split(start["next_action"])
    assert command == ["ep", "study", "scaffold", str(root)]
    neutral = payload(runner.invoke(app, command[1:]))["data"]
    assert neutral["template"] is None
    assert "obtain approval" in neutral["next_action"]
    assert not (root / "workflow-gates.json").exists()
    assert list((root / "edsl_jobs/job_a").iterdir()) == []

    plan = "# Approved plan\nOne respondent; one example question.\n"
    (root / "plan.md").write_text(plan)
    method = payload(runner.invoke(app, [
        "study", "scaffold", str(root), "--template", "survey",
        "--expected-rows", "1", "--required-answer", "example",
        "--model", "test", "--run-description", "Lifecycle test",
    ]))["data"]
    assert method["template"] == "survey"
    assert (root / "plan.md").read_text() == plan
    assert (root / "workflow-gates.json").is_file()
    assert all((root / path).is_file() for path in method["next_edits"])
    assert method["next_action"].startswith("Read and edit every next_edits file")
    assert "prepare" in method["phase_commands"]["after_source_edits"]


def test_study_scaffold_installs_packaged_survey_assets(tmp_path):
    root = tmp_path / "sessions/topic_test/study_a"
    root.mkdir(parents=True)
    result = payload(CliRunner().invoke(app, [
        "study", "scaffold", str(root), "--template", "survey",
        "--expected-rows", "48", "--required-answer", "probe",
        "--model", "gpt-5-nano", "--run-description", "Cognitive test",
    ]))
    assert result["data"]["template"] == "survey"
    assert "prepare" in result["data"]["phase_commands"]["after_source_edits"]
    assert result["data"]["next_action"].startswith("Read and edit every next_edits file")
    assert result["data"]["phase_commands"]["after_inference"].endswith(" post-run")
    for relative in [
        "Makefile", "workflow-gates.json", "analysis/validate_results.py",
        "analysis/plot_style.py", "writeup/report.css", "writeup/ep_logo.pdf",
        "edsl_jobs/job_a/study_survey.py", "edsl_jobs/job_a/study_agent_list.py",
    ]:
        assert (root / relative).is_file(), relative


def test_study_scaffold_wires_scenarios_only_when_requested(tmp_path):
    root = tmp_path / "workspace"
    result = payload(CliRunner().invoke(app, [
        "study", "scaffold", "sessions/topic_test/study_a", "--root", str(root),
        "--template", "survey", "--with-scenarios", "--expected-rows", "48",
        "--required-answer", "probe", "--model", "gpt-5-nano",
        "--run-description", "Cognitive test",
    ]))
    study = root / "sessions/topic_test/study_a"
    scenario_source = study / "edsl_jobs/job_a/study_scenario_list.py"
    makefile = (study / "Makefile").read_text(encoding="utf-8")

    assert result["data"]["with_scenarios"] is True
    assert result["data"]["next_edits"][-1] == "edsl_jobs/job_a/study_scenario_list.py"
    assert scenario_source.is_file()
    assert "SCENARIOS := $(JOB_DIR)/scenario_list.ep" in makefile
    assert "--scenarios $(SCENARIOS)" in makefile
    assert "$(JOBS): $(SURVEY) $(AGENTS) $(SCENARIOS) $(MODELS)" in makefile


@pytest.mark.parametrize("with_scenarios", [False, True])
def test_scaffold_exports_preserve_scenario_metadata_when_requested(tmp_path, with_scenarios):
    from edsl import Agent, Model, QuestionFreeText, Results, Scenario, Survey
    from edsl.results.result import Result

    root = tmp_path / "study with spaces"
    args = ["study", "scaffold", str(root), "--template", "survey",
            "--expected-rows", "1", "--required-answer", "choice", "--model", "test",
            "--run-description", "Offline export fixture"]
    if with_scenarios:
        args.append("--with-scenarios")
    payload(CliRunner().invoke(app, args))
    survey = Survey([QuestionFreeText(question_name="choice", question_text="Choose")])
    results = Results(survey=survey, data=[Result(
        agent=Agent(name="investor", traits={"segment": "aggressive"}),
        scenario=Scenario({"direction": "loss", "magnitude": 25}),
        model=Model("test"), iteration=0, answer={"choice": "buy"}, survey=survey,
    )])
    results.git.save(str(root / "data/results.ep"))
    # Existing Results are the fixture; do not build or execute any Jobs.
    completed = subprocess.run(
        ["make", "-C", str(root), "-o", "data/results.ep", "exports",
         f"EP={shlex.quote(sys.executable)} -m edsl"],
        capture_output=True, text=True, timeout=30,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    with (root / "writeup/tables/results.csv").open() as stream:
        csv_rows = list(csv.DictReader(stream))
    json_rows = json.loads((root / "writeup/tables/results.json").read_text())
    assert csv_rows[0]["answer.choice"] == "buy"
    assert json_rows[0]["answer.choice"] == "buy"
    if with_scenarios:
        assert csv_rows[0]["scenario.direction"] == "loss"
        assert csv_rows[0]["scenario.magnitude"] == "25"
        assert json_rows[0]["scenario.direction"] == "loss"
        assert json_rows[0]["scenario.magnitude"] == 25
    else:
        assert not any(key.startswith("scenario.") for key in csv_rows[0])
        assert not any(key.startswith("scenario.") for key in json_rows[0])


def test_study_scaffold_rejects_scenarios_for_non_survey_template(tmp_path):
    result = CliRunner().invoke(app, [
        "study", "scaffold", str(tmp_path / "study_a"),
        "--template", "agent-list", "--with-scenarios", "--expected-agents", "2",
    ])
    assert result.exit_code == 2
    assert "--with-scenarios requires --template survey" in result.output


def test_study_scaffold_reports_missing_template_invariants(tmp_path):
    result = CliRunner().invoke(app, ["study", "scaffold", str(tmp_path / "study_a"), "--template", "survey"])
    assert result.exit_code == 2
    assert json.loads(result.output)["error"]["code"] == "STUDY_SCAFFOLD_ERROR"

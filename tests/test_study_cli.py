import json
from pathlib import Path

from click.testing import CliRunner

from edsl.__main__ import app


def payload(result):
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_study_start_allocates_next_path_and_creates_neutral_scaffold(tmp_path):
    first = payload(CliRunner().invoke(app, ["study", "start", "--root", str(tmp_path), "--topic", "Cognitive Survey"]))
    assert first["data"]["recommended_study"] == "sessions/topic_cognitive-survey/study_a"
    assert (tmp_path / "sessions/topic_cognitive-survey/study_a").is_dir()
    assert not (tmp_path / "sessions/topic_cognitive-survey/study_a/plan.md").exists()

    second = payload(CliRunner().invoke(app, ["study", "start", "--root", str(tmp_path), "--topic", "Cognitive Survey"]))
    assert second["data"]["recommended_study"] == "sessions/topic_cognitive-survey/study_b"


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

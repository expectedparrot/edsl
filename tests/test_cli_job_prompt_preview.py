import json

from click.testing import CliRunner

from edsl import Agent, Jobs, Model, QuestionFreeText, Scenario, ScenarioList, Survey
from edsl.__main__ import app


def preview(path, *args, code=0):
    result = CliRunner().invoke(app, ["jobs", "preview-prompt", str(path), *args])
    assert result.exit_code == code, (result.output, result.exception)
    return json.loads(result.output)


def test_preview_checks_rendered_text_and_saved_assignment(tmp_path):
    scenarios = ScenarioList([{"lesson": "Geometry"}, {"lesson": "Literature"}])
    q = QuestionFreeText(question_name="clarity", question_text="Rate {{ lesson }}.")
    job = Jobs(
        survey=Survey([q]),
        scenarios=scenarios,
        agents=[Agent(traits={"level": "Advanced"})],
        models=[Model("test")],
    )
    job.set_treatment_assignment(
        {
            "version": 1,
            "conditions": {"A": 0, "B": 1},
            "unit": "agent_iteration",
            "planned_iterations": 2,
            "schedule": {"agent:0|iteration:0": "B", "agent:0|iteration:1": "A"},
        }
    )
    path = tmp_path / "job.ep"
    job.git.save(path)
    original = path.read_bytes()
    first = preview(
        path,
        "clarity",
        "--expect-text",
        "Geometry",
        "--expect-text",
        "Advanced",
        "--forbid-text",
        "Literature",
    )["data"]
    assert first["planned_interviews"] == 2
    assert first["indices"]["scenario"] == 0 and first["iteration"] == 1
    second = preview(
        path, "clarity", "--interview-index", "1", "--expect-text", "Literature"
    )["data"]
    assert second["indices"]["scenario"] == 1 and second["iteration"] == 0
    failure = preview(
        path,
        "clarity",
        "--expect-text",
        "Unseen",
        "--forbid-text",
        "Geometry",
        code=5,
    )["error"]
    assert failure["code"] == "PROMPT_TEXT_MISMATCH"
    case = failure["details"][0]
    assert case["missing_text"] == ["Unseen"] and case["forbidden_text_found"] == [
        "Geometry"
    ]
    assert "Geometry" in case["user_prompt"]
    assert (
        preview(path, "clarity", "--interview-index", "2", code=5)["error"]["code"]
        == "VALIDATION_ERROR"
    )
    assert (
        preview(path, "clarity", "--answers", '{"clarity":1}', code=5)["error"]["code"]
        == "VALIDATION_ERROR"
    )
    assert path.read_bytes() == original


def test_dictionary_scenarios_support_mutation_and_rendering(tmp_path):
    rows = ScenarioList([{"topic": "initial"}])
    existing = Scenario({"topic": "keep"})
    rows.append(existing)
    rows[0] = {"topic": "update"}
    rows[1:] = [existing, {"topic": "last"}]
    assert rows[1] is existing
    assert all(isinstance(s, Scenario) for s in rows)
    q = QuestionFreeText(question_name="read", question_text="Explain {{ topic }}")
    path = tmp_path / "job.ep"
    Jobs(survey=Survey([q]), scenarios=rows, models=[Model("test")]).git.save(path)
    assert (
        "Explain last"
        in preview(path, "read", "--interview-index", "2")["data"]["user_prompt"]
    )


def test_build_can_assert_cardinality_and_pair_aligned_rows(tmp_path):
    from edsl import AgentList

    paths = {
        name: str(tmp_path / f"{name}.ep")
        for name in ("survey", "agents", "scenarios", "job")
    }
    Survey([QuestionFreeText(question_name="q", question_text="{{ topic }}")]).git.save(
        paths["survey"]
    )
    AgentList([Agent(traits={"id": i}) for i in (1, 2)]).git.save(paths["agents"])
    ScenarioList([{"topic": "First"}, {"topic": "Second"}]).git.save(paths["scenarios"])
    args = [
        "jobs",
        "build",
        "--survey",
        paths["survey"],
        "--agents",
        paths["agents"],
        "--scenarios",
        paths["scenarios"],
        "--output",
        paths["job"],
    ]
    runner = CliRunner()
    built = json.loads(runner.invoke(app, args).output)["data"]
    assert (built["assignment_mode"], built["interviews_per_iteration"]) == ("cross", 4)
    original = (tmp_path / "job.ep").read_bytes()
    fail = runner.invoke(app, args + ["--expect-interviews", "2"])
    assert (
        fail.exit_code == 5
        and json.loads(fail.output)["error"]["code"] == "INTERVIEW_COUNT_MISMATCH"
    )
    assert (tmp_path / "job.ep").read_bytes() == original
    paired = json.loads(
        runner.invoke(
            app, args + ["--pair-agents-scenarios", "--expect-interviews", "2"]
        ).output
    )["data"]
    assert (paired["assignment_mode"], paired["interviews_per_iteration"]) == ("zip", 2)
    second = preview(
        paths["job"], "q", "--interview-index", "1", "--expect-text", "Second"
    )["data"]
    assert second["indices"]["agent"] == second["indices"]["scenario"] == 1

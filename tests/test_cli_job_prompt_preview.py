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


def test_inspect_reveals_default_cross_and_surfaces_plan_on_wrong_command(tmp_path):
    q = QuestionFreeText(question_name="clarity", question_text="Rate {{ topic }}.")
    job = Jobs(
        survey=Survey([q]),
        agents=[Agent(traits={"id": i}) for i in range(2)],
        scenarios=ScenarioList([{"topic": "One"}, {"topic": "Two"}]),
        models=[Model("test")],
    )
    runner = CliRunner()
    for mode, expected_count in [("cross", 4), ("zip", 2)]:
        if mode == "zip":
            job.zip_assign()
        path = str(tmp_path / f"{mode} study.ep")
        job.git.save(path)
        info = json.loads(runner.invoke(app, ["inspect", path]).output)["data"]
        assert (info["assignment_mode"], info["interviews_per_iteration"]) == (
            mode,
            expected_count,
        )
        markdown = runner.invoke(app, ["inspect", path, "--markdown"])
        assert markdown.exit_code == 0
        assert (
            f"**Assigned interviews per iteration**  \n{expected_count}"
            in markdown.output
        )
        redirect = runner.invoke(app, ["surveys", "show", path])
        assert redirect.exit_code == 2
        issue = json.loads(redirect.output)["error"]
        assert issue["code"] == "UNSUPPORTED_OBJECT"
        assert issue["details"] == [job.assignment_summary()]
        assert "ep inspect" in issue["suggestion"]


def test_inspect_counts_actual_paired_identifiers_without_disclosing_values():
    agents = [
        Agent(traits={"research_id": v}) for v in ("test-secret-1", "test-secret-2")
    ]
    scenarios = ScenarioList(
        [{"research_id": "test-secret-2"}, {"research_id": "test-secret-1"}]
    )
    survey = Survey(
        [QuestionFreeText(question_name="q", question_text="Review {{ research_id }}.")]
    )
    job = Jobs(
        survey=survey, agents=agents, scenarios=scenarios, models=[Model("test")]
    )
    assert "paired_identifier_counts" not in job.assignment_summary()
    job.zip_assign()
    summary = job.assignment_summary()
    assert summary["paired_identifier_counts"] == {
        "research_id": {"compared": 2, "mismatched": 2}
    }
    assert "test-secret-" not in json.dumps(summary)
    job.scenarios[0], job.scenarios[1] = job.scenarios[1], job.scenarios[0]
    assert (
        job.assignment_summary()["paired_identifier_counts"]["research_id"][
            "mismatched"
        ]
        == 0
    )


def test_preview_verifies_portable_file_input_for_each_question(tmp_path):
    from hashlib import sha256
    from edsl import FileStore

    source = tmp_path / "notes.txt"
    payload = b"Notes for this study"
    source.write_bytes(payload)
    survey = Survey(
        [
            QuestionFreeText(
                question_name="read", question_text="Read {{ scenario.asset }}."
            ),
            QuestionFreeText(
                question_name="missed", question_text="What does the attachment say?"
            ),
        ]
    )
    job = Jobs(
        survey=survey,
        scenarios=ScenarioList([{"asset": FileStore(str(source))}]),
        models=[Model("test")],
    )
    path = tmp_path / "job.ep"
    job.git.save(path)
    source.unlink()
    attachments = preview(path, "read", "--expect-files", "1")["data"]["attachments"]
    assert attachments == [
        {
            "name": "notes.txt",
            "mime_type": "text/plain",
            "size_bytes": len(payload),
            "sha256": sha256(payload).hexdigest(),
        }
    ]
    issue = preview(path, "missed", "--expect-files", "1", code=5)["error"]
    assert issue["code"] == "PROMPT_ATTACHMENT_MISMATCH"
    assert issue["details"][0]["attachments"] == []


def test_conditional_files_follow_the_rendered_branch_in_display_order(tmp_path):
    from hashlib import sha256

    from edsl import FileStore

    assets = {}
    digests = {}
    for name in ("full", "crop", "ref"):
        source = tmp_path / f"{name}.txt"
        source.write_text(name)
        assets[name] = FileStore(str(source))
        digests[name] = sha256(source.read_bytes()).hexdigest()
    question = QuestionFreeText(
        question_name="compare",
        question_text=(
            "{{ scenario }}. Literal <see file full>. {{ scenario.ref }} "
            "{% if open %}{{ full }}{% else %}{{ scenario.crop }}{% endif %} {{ ref }}"
        ),
    )
    job = Jobs(
        survey=Survey(
            [
                question,
                QuestionFreeText(
                    question_name="inline_choice",
                    question_text="{{ (scenario['full'] if open else scenario.crop) | upper }}",
                ),
            ]
        ),
        models=[Model("test")],
        scenarios=ScenarioList([dict(assets, open=False), dict(assets, open=True)]),
    )
    path = tmp_path / "exhibits.ep"
    job.git.save(path)
    for i, name in enumerate(["crop", "full"]):
        data = preview(
            path,
            "compare",
            "--interview-index",
            str(i),
            "--expect-file-sha256",
            digests["ref"].upper(),
            "--expect-file-sha256",
            digests[name],
        )["data"]
        assert [a["name"] for a in data["attachments"]] == ["ref.txt", f"{name}.txt"]
        assert (
            f"Literal <see file full>. <see file ref> <see file {name}> <see file ref>"
            in data["user_prompt"]
        )
        inline = preview(
            path,
            "inline_choice",
            "--interview-index",
            str(i),
            "--expect-file-sha256",
            digests[name],
        )["data"]
        assert f"<see file {name}>".upper() in inline["user_prompt"]
    issue = preview(
        path,
        "compare",
        "--expect-file-sha256",
        digests["crop"],
        "--expect-file-sha256",
        digests["ref"],
        code=5,
    )["error"]
    assert issue["code"] == "PROMPT_ATTACHMENT_MISMATCH"
    assert issue["details"][0]["expected_sha256"] == [digests["crop"], digests["ref"]]
    assert (
        preview(path, "compare", "--expect-file-sha256", "bad", code=5)["error"]["code"]
        == "VALIDATION_ERROR"
    )

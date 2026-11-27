"""CLI tests for starting and synchronizing Humanize workflow experiments."""

import json

from click.testing import CliRunner

from edsl import Agent, QuestionFreeText, Survey
from edsl.__main__ import app
from edsl.workflows import ExecutionPlan, Workflow, WorkflowExperiment, human, role


class FakeHumanizeResponse:
    def __init__(self, answer):
        self.answer = answer


class FakeCoop:
    surveys = {}
    next_id = 0

    def create_human_survey(self, *, survey, agent_list, **kwargs):
        type(self).next_id += 1
        survey_id = f"survey-{type(self).next_id}"
        type(self).surveys[survey_id] = {
            "survey": survey,
            "agent": agent_list[0],
            "answer": None,
        }
        return {"uuid": survey_id}

    def create_human_survey_delivery(self, survey_id, *, name):
        return {"delivery_uuid": f"delivery-{survey_id}"}

    def get_human_survey(self, survey_id):
        return {"n_responses": int(self.surveys[survey_id]["answer"] is not None)}

    def get_human_survey_responses(self, survey_id):
        return [FakeHumanizeResponse(self.surveys[survey_id]["answer"])]


def human_experiment(*, email="proposer@example.com"):
    builder = Workflow("CLI human workflow")
    question = QuestionFreeText(
        question_name="suggestion", question_text="Suggest an activity."
    )
    builder.step("suggest", Survey([question]), assigned_to=role("proposer"))
    participant = Agent(
        name="proposer@example.com",
        traits={"role": "proposer", "email": email},
    )
    plan = ExecutionPlan().bind(role("proposer"), human())
    return WorkflowExperiment(builder.compile(), [], [participant], plan)


def test_start_sync_and_status_drive_humanize_workflow(tmp_path, monkeypatch):
    FakeCoop.surveys = {}
    FakeCoop.next_id = 0
    monkeypatch.setattr("edsl.coop.Coop", FakeCoop)
    experiment_path = tmp_path / "experiment.json"
    human_experiment().save(experiment_path)
    run_dir = tmp_path / "human-run"
    runner = CliRunner()

    started = runner.invoke(
        app,
        [
            "orchestration",
            "start",
            "--file",
            str(experiment_path),
            "--output",
            str(run_dir),
        ],
    )
    assert started.exit_code == 0, started.output
    started_data = json.loads(started.output)["data"]
    assert started_data["status"] == "running"
    assert started_data["ready_items"] == 1
    assert (run_dir / "run.json").exists()

    sent = runner.invoke(app, ["orchestration", "sync", "--output", str(run_dir)])
    assert sent.exit_code == 0, sent.output
    sent_data = json.loads(sent.output)["data"]
    assert sent_data["deliveries"] == ["survey-1"]
    assert sent_data["imported_responses"] == 0
    assert (
        "Suggest an activity."
        in FakeCoop.surveys["survey-1"]["survey"].questions[0].question_text
    )

    FakeCoop.surveys["survey-1"]["answer"] = {"suggestion": "Sailing"}
    imported = runner.invoke(app, ["orchestration", "sync", "--output", str(run_dir)])
    assert imported.exit_code == 0, imported.output
    assert json.loads(imported.output)["data"]["imported_responses"] == 1

    status = runner.invoke(app, ["orchestration", "status", "--output", str(run_dir)])
    assert status.exit_code == 0, status.output
    status_data = json.loads(status.output)["data"]
    assert status_data["status"] == "completed"
    assert status_data["item_counts"] == {"completed": 1}


def test_humanize_start_requires_email_and_empty_run_directory(tmp_path):
    experiment_path = tmp_path / "experiment.json"
    human_experiment(email="").save(experiment_path)
    output_dir = tmp_path / "run"
    invocation = CliRunner().invoke(
        app,
        [
            "orchestration",
            "start",
            "--file",
            str(experiment_path),
            "--output",
            str(output_dir),
        ],
    )
    assert invocation.exit_code == 5
    envelope = json.loads(invocation.output)
    assert envelope["error"]["code"] == "VALIDATION_ERROR"
    assert not output_dir.exists()


def test_status_rejects_modified_pinned_experiment(tmp_path, monkeypatch):
    monkeypatch.setattr("edsl.coop.Coop", FakeCoop)
    experiment_path = tmp_path / "experiment.json"
    human_experiment().save(experiment_path)
    run_dir = tmp_path / "human-run"
    start = CliRunner().invoke(
        app,
        [
            "orchestration",
            "start",
            "--file",
            str(experiment_path),
            "--output",
            str(run_dir),
        ],
    )
    assert start.exit_code == 0, start.output
    pinned = json.loads((run_dir / "experiment.json").read_text())
    pinned["metadata"]["changed"] = True
    (run_dir / "experiment.json").write_text(json.dumps(pinned))

    status = CliRunner().invoke(
        app, ["orchestration", "status", "--output", str(run_dir)]
    )
    assert status.exit_code == 5
    assert json.loads(status.output)["error"]["code"] == "VALIDATION_ERROR"


def test_check_item_reads_the_committed_question_and_answer(tmp_path):
    from edsl.workflows import scripted

    builder = Workflow("Peer handoff")
    reader = builder.step("review", Survey([QuestionFreeText(
        question_name="note", question_text="What should change?"
    )]), assigned_to=role("reader"))
    editor = builder.step("decide", Survey([QuestionFreeText(
        question_name="decision", question_text="Respond to " + reader.answer("note").template
    )]), assigned_to=role("editor"), after=reader)
    builder.step("revise", Survey([QuestionFreeText(question_name="revision", question_text="Revise it.")]),
                 assigned_to=role("reader"), after=editor, when=editor.answer("decision").equals("Revise"))
    agents = [
        Agent(name=n, traits={"role": r})
        for n, r in [("Mira", "reader"), ("Eden", "editor")]
    ]
    plan = (
        ExecutionPlan()
        .bind(role("reader"), human())
        .bind(role("editor"), scripted(answers={"decision": "Accept"}))
    )
    definition = tmp_path / "protocol.json"
    WorkflowExperiment(builder.compile(), [], agents, plan).save(definition)
    responses = tmp_path / "responses.json"
    responses.write_text(
        json.dumps(
            [
                {
                    "step": "review",
                    "participant": "Mira",
                    "answers": {"note": "Check weekday coverage."},
                },
                {
                    "step": "decide",
                    "participant": "Eden",
                    "answers": {"decision": "Revise"},
                },
            ]
        )
    )
    run = tmp_path / "pilot run"
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "orchestration",
            "run",
            "--file",
            str(definition),
            "--output",
            str(run),
            "--responses",
            str(responses),
            "--instance-id",
            "pilot",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output)
    assert envelope["data"]["scripted_replay_participants"] == ["Eden"]
    assert (
        envelope["warnings"]
        and "--instance-id pilot" in envelope["data"]["check_item_command"]
    )
    path = run / "workflow.sqlite"
    original = path.read_bytes()
    prefix = ["orchestration", "check-item", str(run), "--instance-id", "pilot"]
    args = prefix + ["--step", "decide", "--participant", "Eden"]
    result = runner.invoke(
        app,
        args
        + [
            "--question",
            "decision",
            "--expect-text",
            "Check weekday coverage.",
            "--expect-answers",
            '{"decision":"Accept"}',
            "--expect-status",
            "completed",
        ],
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)["data"]
    assert data["questions"] == {"decision": "Respond to Check weekday coverage."}
    assert data["submitted"] and data["answer_keys"] == ["decision"]
    bad = runner.invoke(
        app,
        args
        + ["--expect-answers", '{"decision":"Revise"}', "--forbid-text", "coverage"],
    )
    issue = json.loads(bad.output)["error"]
    assert bad.exit_code == 5 and issue["details"][0]["mismatched_answers"] == [
        "decision"
    ]
    assert runner.invoke(app, args + ["--question", "absent"]).exit_code == 3
    skipped = prefix + ["--step", "revise", "--participant", "Mira"]
    assert runner.invoke(app, skipped + ["--expect-status", "skipped"]).exit_code == 0
    assert runner.invoke(app, skipped + ["--forbid-text", "private"]).exit_code == 5
    assert (
        runner.invoke(
            app, prefix + ["--step", "decide", "--participant", "Mira"]
        ).exit_code
        == 3
    )
    assert path.read_bytes() == original


def test_check_item_on_an_empty_directory_creates_no_database(tmp_path):
    args = [
        "orchestration",
        "check-item",
        str(tmp_path),
        "--step",
        "review",
        "--participant",
        "Mira",
    ]
    result = CliRunner().invoke(app, args)
    assert result.exit_code == 3 and not (tmp_path / "workflow.sqlite").exists()

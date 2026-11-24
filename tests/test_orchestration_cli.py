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

from examples.workflow_weekend_activity_revision import run
from edsl.workflows import WorkflowDAGVisualization


class RevisionScript:
    def answer(self, agent, opened):
        if opened.step_name == "propose-1":
            return {"suggestion_1": "Sailing"}
        if opened.step_name == "approve-1":
            assert "Sailing" in opened.survey.questions[0].question_text
            return {"approved_1": "No"}
        if opened.step_name == "propose-2":
            assert opened.shared_state["activity"]["suggestions"] == ["Sailing"]
            return {"suggestion_2": "Hiking"}
        assert opened.step_name == "approve-2"
        assert "Hiking" in opened.survey.questions[0].question_text
        return {"approved_2": "Yes"}


def test_rejection_releases_revision_and_approval_skips_future_rounds(tmp_path):
    store, instance_id, simulation = run(tmp_path, RevisionScript())

    assert [message.participant_id for message in simulation.inbox.messages] == [
        "proposer@simulated.email",
        "approver@simulated.email",
        "proposer@simulated.email",
        "approver@simulated.email",
    ]
    statuses = {item["step_name"]: item["status"] for item in store.items(instance_id)}
    assert statuses == {
        "propose-1": "completed",
        "approve-1": "completed",
        "propose-2": "completed",
        "approve-2": "completed",
        "propose-3": "skipped",
        "approve-3": "skipped",
        "propose-4": "skipped",
        "approve-4": "skipped",
    }
    assert store.events(instance_id)[-1]["kind"] == "workflow.completed"


def test_completed_workflow_renders_as_standalone_dag(tmp_path):
    store, instance_id, simulation = run(tmp_path, RevisionScript())
    output = WorkflowDAGVisualization(simulation.coordinator, instance_id).save(
        tmp_path / "workflow.html"
    )
    html = output.read_text()

    assert "weekend-activity-revision" in html
    assert "proposer@simulated.email" in html
    assert "Sailing" in html and "Hiking" in html
    assert "Completed 4" in html
    assert "Skipped 4" in html
    assert "const edges=" in html

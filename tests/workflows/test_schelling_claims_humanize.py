from edsl.workflows import HumanWorkflow, SQLiteWorkflowStore, WorkflowCoordinator
from examples.workflow_schelling_claims_humanize import build_workflow, participants


def test_schelling_email_workflow_round_trips_and_releases_two_claims(tmp_path):
    workflow = HumanWorkflow.from_dict(build_workflow().to_dict())
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    coordinator = WorkflowCoordinator(workflow, store)
    instance = coordinator.launch(participants())

    ready = store.items(instance, step_name="claim")
    notices = store.items(instance, step_name="payoff-notice")
    assert {item["participant_id"] for item in ready} == {
        "john.joseph.horton+p1@gmail.com",
        "john.joseph.horton+p2@gmail.com",
    }
    assert {item["status"] for item in ready} == {"ready"}
    assert {item["status"] for item in notices} == {"blocked"}

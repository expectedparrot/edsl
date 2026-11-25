from edsl.workflows import HumanWorkflow, SQLiteWorkflowStore, WorkflowCoordinator
from edsl.examples.workflows.workflow_schelling_claims_humanize import build_workflow, participants


def test_schelling_email_workflow_round_trips_and_releases_two_claims(tmp_path):
    workflow = HumanWorkflow.from_dict(build_workflow().to_dict())
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    coordinator = WorkflowCoordinator(workflow, store)
    instance = coordinator.launch(participants(("player1@example.com", "player2@example.com")))

    ready = store.items(instance, step_name="claim")
    notices = store.items(instance, step_name="payoff-notice")
    assert {item["participant_id"] for item in ready} == {"player-1", "player-2"}
    assert {item["status"] for item in ready} == {"ready"}
    assert {item["status"] for item in notices} == {"blocked"}

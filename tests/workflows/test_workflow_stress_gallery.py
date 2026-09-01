from examples.workflow_stress_gallery import cases
from edsl.sharedstate import SQLiteStateBackend
from edsl.workflows import HumanWorkflow, SQLiteWorkflowStore, WorkflowCoordinator


def test_gallery_cases_are_portable_and_launch_with_expected_initial_fanout(tmp_path):
    expected_ready = {
        "brainstorm": 3,
        "blind-review": 1,
        "escalation": 1,
        "editorial": 1,
        "procurement": 3,
        "moderation": 3,
        "translation": 1,
    }
    for case in cases():
        workflow = HumanWorkflow.from_dict(case.workflow.to_dict())
        root = tmp_path / case.slug
        store = SQLiteWorkflowStore(root / "workflow.sqlite")
        backends = {
            state_map.state_id: SQLiteStateBackend(
                state_map, root / f"{state_map.state_id}.sqlite"
            )
            for state_map in case.state_maps
        }
        coordinator = WorkflowCoordinator(workflow, store, state_backends=backends)
        instance_id = coordinator.launch(case.agents)

        ready = [item for item in store.items(instance_id) if item["status"] == "ready"]
        assert len(ready) == expected_ready[case.slug]

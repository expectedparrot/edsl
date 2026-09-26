from examples.workflow_weekend_activity_approval import (
    APPROVER_EMAIL,
    PROPOSER_EMAIL,
    run_demo,
)
from edsl.workflows import HumanizeDeliveryAdapter, OutboxDispatcher


class FakeResponse:
    def __init__(self, answer):
        self.answer = answer


class FakeCoop:
    def __init__(self):
        self.surveys = {}
        self.deliveries = []

    def create_human_survey(self, *, survey, agent_list, **kwargs):
        survey_id = f"survey-{len(self.surveys) + 1}"
        self.surveys[survey_id] = {
            "survey": survey,
            "agent": agent_list[0],
            "answer": None,
        }
        return {"uuid": survey_id}

    def create_human_survey_delivery(self, survey_id, *, name):
        self.deliveries.append((survey_id, name))
        return {"delivery_uuid": f"delivery-{len(self.deliveries)}"}

    def get_human_survey(self, survey_id):
        return {"n_responses": int(self.surveys[survey_id]["answer"] is not None)}

    def get_human_survey_responses(self, survey_id):
        return [FakeResponse(self.surveys[survey_id]["answer"])]


def test_weekend_activity_is_proposed_before_approval(tmp_path):
    events, messages = run_demo(tmp_path)

    assert [message.participant_id for message in messages] == [
        PROPOSER_EMAIL,
        APPROVER_EMAIL,
    ]
    completed = [
        event["step_name"] for event in events if event["kind"] == "work_item.completed"
    ]
    assert completed == ["suggest-activity", "approve-activity"]
    assert events[-1]["kind"] == "workflow.completed"


def test_humanize_adapter_delivers_second_email_only_after_first_response(tmp_path):
    from examples.workflow_weekend_activity_approval import build_workflow, participants
    from edsl.sharedstate import SQLiteStateBackend
    from edsl.workflows import SQLiteWorkflowStore, WorkflowCoordinator

    workflow, state_map = build_workflow()
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    coordinator = WorkflowCoordinator(
        workflow,
        store,
        state_backends={
            state_map.state_id: SQLiteStateBackend(state_map, tmp_path / "state.sqlite")
        },
    )
    instance_id = coordinator.launch(participants())
    coop = FakeCoop()
    adapter = HumanizeDeliveryAdapter(coordinator, coop)
    dispatcher = OutboxDispatcher(store, adapter)

    dispatcher.dispatch()
    assert [entry["agent"].name for entry in coop.surveys.values()] == [PROPOSER_EMAIL]

    coop.surveys["survey-1"]["answer"] = {"suggestion": "Hiking"}
    assert adapter.poll_completed() == 1
    dispatcher.dispatch()

    assert [entry["agent"].name for entry in coop.surveys.values()] == [
        PROPOSER_EMAIL,
        APPROVER_EMAIL,
    ]
    assert "Hiking" in coop.surveys["survey-2"]["survey"].questions[0].question_text
    coop.surveys["survey-2"]["answer"] = {"approved": "Yes"}
    assert adapter.poll_completed() == 1
    assert store.events(instance_id)[-1]["kind"] == "workflow.completed"

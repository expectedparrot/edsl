from __future__ import annotations

from datetime import timedelta

import pytest

from edsl import Agent, Model, QuestionFreeText, Survey
from edsl.sharedstate import (
    Command,
    Machine,
    SQLiteStateBackend,
    SharedState,
    SharedStateMap,
    T,
    append,
    current,
    field,
    input_,
    record,
    state_field,
)
from edsl.workflows import (
    DeliveryReceipt,
    EDSLAgentAnswerer,
    HumanStep,
    HumanWorkflow,
    OutboxDispatcher,
    ParticipantSelector,
    RetryPolicy,
    SQLiteWorkflowStore,
    WorkflowCoordinator,
    WorkflowSimulation,
    ExecutionPlan,
    human,
    llm,
    role,
)


def test_simulation_routes_answerers_through_execution_plan(tmp_path):
    question = QuestionFreeText(question_name="reply", question_text="Reply.")
    workflow = HumanWorkflow("routed", [HumanStep("reply", Survey([question]))])
    store = SQLiteWorkflowStore(tmp_path / "routed.sqlite")
    coordinator = WorkflowCoordinator(workflow, store)
    agent = Agent(name="person", traits={"role": "person"})
    instance = coordinator.launch([agent])

    class Answerer:
        def __init__(self, value): self.value = value
        def answer(self, agent, opened): return {"reply": self.value}

    plan = ExecutionPlan().bind(role("person"), human(channel="email"))
    WorkflowSimulation(
        coordinator, {agent.name: agent}, Answerer("fallback"),
        execution_plan=plan,
        answerers={"human": Answerer("human-route"), "llm": Answerer("llm-route")},
    ).run(instance)
    assert store.step_answers(instance, "reply") == [{"reply": "human-route"}]
    assert store.executor(store.items(instance)[0]["id"]) == {
        "kind": "human", "options": {"channel": "email"}
    }


class ScriptedAnswerer:
    def answer(self, agent, opened):
        if opened.step_name == "review":
            return {"decision": agent.traits["decision"]}
        return {"resolution": "include"}


class CaptureDeliveryAdapter:
    def __init__(self):
        self.requests = []

    def deliver(self, request):
        self.requests.append(request)
        return DeliveryReceipt(external_id=f"email:{request.work_item_id}")


def test_two_reviews_fan_in_before_adjudication_and_write_shared_state(tmp_path):
    definition = Machine(
        name="ReviewLog",
        constants={},
        fields={"reviews": state_field(T.sequence(), [])},
        commands={
            "record": Command(
                inputs={"reviewer": T.text(), "decision": T.text()},
                effects=(
                    append(
                        "reviews",
                        record(
                            reviewer=input_("reviewer"),
                            decision=input_("decision"),
                        ),
                    ),
                ),
            )
        },
        view={"reviews": field("reviews")},
    )
    state_map = SharedStateMap(SharedState(log=definition), state_id="reviews")
    log = state_map.by("paper-1").log
    decision = QuestionFreeText(
        question_name="decision", question_text="Include or exclude this paper?"
    )
    resolution = QuestionFreeText(
        question_name="resolution",
        question_text="Resolve these independent reviews: {{ shared_state.log.reviews }}",
    )
    workflow = HumanWorkflow(
        "double-screen",
        [
            HumanStep(
                "review",
                Survey([decision]),
                ParticipantSelector.role("reviewer"),
                writes=(
                    log.record(
                        reviewer=current.agent.name,
                        decision=decision.answer,
                    ),
                ),
            ),
            HumanStep(
                "adjudicate",
                Survey([resolution]),
                ParticipantSelector.role("adjudicator"),
                after=("review",),
                reads=(log.read(),),
            ),
        ],
    )
    # Workflow definitions, including surveys and shared-state operations, are portable.
    workflow = HumanWorkflow.from_dict(workflow.to_dict())
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    backend = SQLiteStateBackend(state_map, tmp_path / "state.sqlite")
    coordinator = WorkflowCoordinator(
        workflow, store, state_backends={"reviews": backend}
    )
    agents = [
        Agent(name="reviewer-a", traits={"role": "reviewer", "decision": "include"}),
        Agent(name="reviewer-b", traits={"role": "reviewer", "decision": "exclude"}),
        Agent(name="editor", traits={"role": "adjudicator"}),
    ]
    instance_id = coordinator.launch(agents)

    assert [
        item["step_name"]
        for item in store.items(instance_id)
        if item["status"] == "ready"
    ] == ["review", "review"]
    simulation = WorkflowSimulation(
        coordinator,
        {agent.name: agent for agent in agents},
        ScriptedAnswerer(),
        response_delay=timedelta(hours=2),
    )
    simulation.run(instance_id)

    assert [message.participant_id for message in simulation.inbox.messages] == [
        "reviewer-a",
        "reviewer-b",
        "editor",
    ]
    assert simulation.clock.now.hour == 4
    assert all(item["status"] == "completed" for item in store.items(instance_id))
    kinds = [event["kind"] for event in store.events(instance_id)]
    assert kinds.count("workflow.completed") == 1
    assert kinds[-1] == "workflow.completed"


def test_edsl_agent_answerer_uses_normal_local_survey_pipeline(tmp_path):
    question = QuestionFreeText(question_name="reply", question_text="Reply now.")
    workflow = HumanWorkflow("one", [HumanStep("reply", Survey([question]))])
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    coordinator = WorkflowCoordinator(workflow, store)
    agent = Agent(name="respondent")
    instance_id = coordinator.launch([agent])
    simulation = WorkflowSimulation(
        coordinator,
        {agent.name: agent},
        EDSLAgentAnswerer(Model("test", canned_response="received")),
    )

    simulation.run(instance_id)

    submissions = store.rows("SELECT answers FROM workflow_submissions")
    assert '"reply": "received"' in submissions[0]["answers"]


def test_submission_retry_is_idempotent(tmp_path):
    question = QuestionFreeText(question_name="reply", question_text="Reply.")
    workflow = HumanWorkflow("one", [HumanStep("reply", Survey([question]))])
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    coordinator = WorkflowCoordinator(workflow, store)
    instance_id = coordinator.launch([Agent(name="person")])
    item_id = store.items(instance_id)[0]["id"]
    coordinator.open(item_id)

    coordinator.submit(item_id, {"reply": "yes"}, idempotency_key="request-1")
    coordinator.submit(item_id, {"reply": "yes"}, idempotency_key="request-1")

    assert len(store.rows("SELECT * FROM workflow_submissions")) == 1
    assert [event["kind"] for event in store.events(instance_id)].count(
        "work_item.completed"
    ) == 1


def test_delivery_adapter_is_thin_and_outbox_driven(tmp_path):
    question = QuestionFreeText(question_name="reply", question_text="Reply.")
    workflow = HumanWorkflow("one", [HumanStep("reply", Survey([question]))])
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    coordinator = WorkflowCoordinator(workflow, store)
    coordinator.launch([Agent(name="person")])
    adapter = CaptureDeliveryAdapter()

    receipts = OutboxDispatcher(store, adapter).dispatch()

    assert len(receipts) == 1
    assert adapter.requests[0].participant_id == "person"
    assert store.pending_outbox() == []


def test_retryable_failure_is_persisted_and_then_succeeds(tmp_path):
    question = QuestionFreeText(question_name="reply", question_text="Reply.")
    workflow = HumanWorkflow("retry", [HumanStep("reply", Survey([question]))])
    store = SQLiteWorkflowStore(tmp_path / "retry.sqlite")
    coordinator = WorkflowCoordinator(workflow, store)
    agent = Agent(name="person")
    instance_id = coordinator.launch([agent])

    class FlakyAnswerer:
        calls = 0

        def answer(self, agent, opened):
            self.calls += 1
            if self.calls == 1:
                raise TimeoutError("temporary timeout")
            return {"reply": "recovered"}

    simulation = WorkflowSimulation(coordinator, {agent.name: agent}, FlakyAnswerer())
    simulation.run(
        instance_id,
        retry_policy=RetryPolicy(max_attempts=2, lease_seconds=30),
    )

    item = store.items(instance_id)[0]
    assert store.item_answers(item["id"]) == {"reply": "recovered"}
    assert [attempt["status"] for attempt in store.attempts(item["id"])] == [
        "failed",
        "succeeded",
    ]
    kinds = [event["kind"] for event in store.events(instance_id)]
    assert "work_item.retry_scheduled" in kinds


def test_fresh_simulation_resumes_an_expired_lease(tmp_path):
    question = QuestionFreeText(question_name="reply", question_text="Reply.")
    workflow = HumanWorkflow("resume", [HumanStep("reply", Survey([question]))])
    path = tmp_path / "resume.sqlite"
    store = SQLiteWorkflowStore(path)
    coordinator = WorkflowCoordinator(workflow, store)
    agent = Agent(name="person")
    instance_id = coordinator.launch([agent])
    outbox = store.pending_outbox()[0]
    store.mark_delivered(outbox["id"])
    item_id = outbox["work_item_id"]
    store.start_attempt(item_id, lease_seconds=300)
    with store.connect() as db:
        db.execute(
            "UPDATE workflow_attempts SET lease_expires_at = ? WHERE work_item_id = ?",
            ("2000-01-01T00:00:00+00:00", item_id),
        )

    restarted_store = SQLiteWorkflowStore(path)
    restarted = WorkflowCoordinator(
        HumanWorkflow.from_dict(workflow.to_dict()), restarted_store
    )

    class Answerer:
        def answer(self, agent, opened):
            return {"reply": "after restart"}

    WorkflowSimulation(restarted, {agent.name: agent}, Answerer()).run(
        instance_id,
        resume=True,
        retry_policy=RetryPolicy(max_attempts=2),
    )
    attempts = restarted_store.attempts(item_id)
    assert [attempt["status"] for attempt in attempts] == [
        "abandoned",
        "succeeded",
    ]
    assert restarted_store.item_answers(item_id) == {"reply": "after restart"}


def test_exhausted_attempts_fail_item_and_instance(tmp_path):
    question = QuestionFreeText(question_name="reply", question_text="Reply.")
    workflow = HumanWorkflow("failure", [HumanStep("reply", Survey([question]))])
    store = SQLiteWorkflowStore(tmp_path / "failure.sqlite")
    coordinator = WorkflowCoordinator(workflow, store)
    agent = Agent(name="person")
    instance_id = coordinator.launch([agent])

    class BrokenAnswerer:
        def answer(self, agent, opened):
            raise RuntimeError("permanent failure")

    simulation = WorkflowSimulation(coordinator, {agent.name: agent}, BrokenAnswerer())
    with pytest.raises(RuntimeError, match="workflow execution failed"):
        simulation.run(
            instance_id,
            retry_policy=RetryPolicy(max_attempts=2, retryable=("exception",)),
        )
    item = store.items(instance_id)[0]
    assert item["status"] == "failed"
    assert len(store.attempts(item["id"])) == 2
    assert store.rows("SELECT status FROM workflow_instances")[0]["status"] == "failed"


def test_retry_policy_is_serializable():
    policy = RetryPolicy(
        max_attempts=4,
        lease_seconds=90,
        retryable=("timeout", "remote_error"),
    )
    assert RetryPolicy.from_dict(policy.to_dict()) == policy

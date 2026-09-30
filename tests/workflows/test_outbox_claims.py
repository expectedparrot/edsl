from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from edsl import Agent, QuestionFreeText, Survey
from edsl.workflows import (
    DeliveryReceipt,
    ExecutionPlan,
    HumanStep,
    HumanWorkflow,
    OutboxDispatcher,
    RoutedOutboxDispatcher,
    SQLiteWorkflowStore,
    WorkflowCoordinator,
    human,
    role,
)


def setup_store(tmp_path):
    store = SQLiteWorkflowStore(tmp_path / "workflow.sqlite")
    workflow = HumanWorkflow(
        "one",
        [
            HumanStep(
                "reply",
                Survey(
                    [
                        QuestionFreeText(question_name="reply", question_text="Reply."),
                    ]
                ),
            )
        ],
    )
    WorkflowCoordinator(workflow, store).launch(
        [
            Agent(name="person", traits={"role": "person"}),
        ],
        instance_id="one",
    )
    return store


def dispatcher(store, adapter, routed):
    if routed:
        plan = ExecutionPlan().bind(role("person"), human())
        return RoutedOutboxDispatcher(store, plan, {"human": adapter})
    return OutboxDispatcher(store, adapter)


@pytest.mark.parametrize("routed", [False, True])
def test_concurrent_dispatchers_deliver_stale_pending_row_only_once(tmp_path, routed):
    store = setup_store(tmp_path)
    barrier = Barrier(2)
    calls = []

    class RacingStore(SQLiteWorkflowStore):
        def pending_outbox(self):
            rows = super().pending_outbox()
            barrier.wait(timeout=5)
            return rows

    class Adapter:
        def deliver(self, request):
            calls.append(request)
            return DeliveryReceipt("external")

    def dispatch():
        return dispatcher(RacingStore(store.path), Adapter(), routed).dispatch()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: dispatch(), range(2)))
    assert sum(map(len, results)) == 1
    assert len(calls) == 1
    assert store.pending_outbox() == []
    assert store.rows("SELECT status FROM workflow_outbox")[0]["status"] == "delivered"
    assert store.rows("SELECT * FROM workflow_outbox_claims") == []


@pytest.mark.parametrize("routed", [False, True])
def test_ambiguous_delivery_survives_restart_until_reconciled(tmp_path, routed):
    store = setup_store(tmp_path)
    calls = []

    class Adapter:
        def deliver(self, request):
            calls.append(request)
            raise TimeoutError("external side effect may have succeeded")

    with pytest.raises(TimeoutError):
        dispatcher(store, Adapter(), routed).dispatch()
    restarted = SQLiteWorkflowStore(store.path)
    assert dispatcher(restarted, Adapter(), routed).dispatch() == []
    assert len(calls) == 1
    claim = restarted.rows("SELECT * FROM workflow_outbox_claims")[0]
    restarted.mark_delivered(claim["outbox_id"], claim_token=claim["token"])
    assert (
        restarted.rows("SELECT status FROM workflow_outbox")[0]["status"] == "delivered"
    )


def test_claim_ownership_fences_retries_and_acknowledgements(tmp_path):
    store = setup_store(tmp_path)
    row = store.pending_outbox()[0]
    token = store.claim_outbox(row["id"])
    assert token is not None
    assert store.claim_outbox(row["id"]) is None
    assert store.pending_outbox() == []
    with pytest.raises(ValueError, match="owned"):
        store.mark_delivered(row["id"])
    with pytest.raises(ValueError, match="owned"):
        store.release_outbox_claim(row["id"], claim_token="wrong")
    store.release_outbox_claim(row["id"], claim_token=token)
    new_token = store.claim_outbox(row["id"])
    assert new_token != token
    with pytest.raises(ValueError, match="owned"):
        store.mark_delivered(row["id"], claim_token=token)
    store.mark_delivered(row["id"], claim_token=new_token)
    assert store.claim_outbox(row["id"]) is None
    with pytest.raises(ValueError, match="pending"):
        store.mark_delivered(row["id"])


@pytest.mark.parametrize("change", ["skip", "pause", "complete"])
def test_claim_rechecks_workflow_state_after_pending_read(tmp_path, change):
    store = setup_store(tmp_path)
    row = store.pending_outbox()[0]
    if change == "skip":
        store.skip(row["work_item_id"], reason="cancelled")
    else:
        with store.connect() as db:
            db.execute(
                "UPDATE workflow_instances SET status=?",
                ("paused" if change == "pause" else "completed",),
            )
    assert store.claim_outbox(row["id"]) is None


def test_terminal_item_is_not_offered_for_delivery(tmp_path):
    store = setup_store(tmp_path)
    row = store.pending_outbox()[0]
    with store.connect() as db:
        db.execute(
            "UPDATE workflow_items SET status = 'completed' WHERE id = ?",
            (row["work_item_id"],),
        )
    assert store.pending_outbox() == []
    assert store.claim_outbox(row["id"]) is None


def test_reconciled_claim_can_be_retried(tmp_path):
    store = setup_store(tmp_path)
    row = store.pending_outbox()[0]
    token = store.claim_outbox(row["id"])
    store.release_outbox_claim(row["id"], claim_token=token)
    calls = []

    class Adapter:
        def deliver(self, request):
            calls.append(request)
            return DeliveryReceipt("external")

    assert OutboxDispatcher(store, Adapter()).dispatch() == [
        DeliveryReceipt("external")
    ]
    assert len(calls) == 1
    assert store.pending_outbox() == []

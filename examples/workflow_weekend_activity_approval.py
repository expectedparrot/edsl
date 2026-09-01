"""Two-person weekend activity proposal and approval workflow.

Run locally with simulated respondents:

    python examples/workflow_weekend_activity_approval.py

Replace the simulation answerer with a Humanize-backed DeliveryAdapter to send
the same ready work items to the two real email addresses.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import time

from edsl import Agent, QuestionMultipleChoice, QuestionYesNo, Survey
from edsl.sharedstate import (
    Command,
    Machine,
    SQLiteStateBackend,
    SharedState,
    SharedStateMap,
    T,
    field,
    input_,
    set_once,
    state_field,
)
from edsl.workflows import (
    HumanStep,
    HumanWorkflow,
    ParticipantSelector,
    SQLiteWorkflowStore,
    WorkflowCoordinator,
    WorkflowSimulation,
    HumanizeDeliveryAdapter,
    OutboxDispatcher,
)


PROPOSER_EMAIL = "john.joseph.horton@gmail.com"
APPROVER_EMAIL = "jjhorton@mit.edu"


def build_workflow():
    activity_state = Machine(
        name="WeekendActivity",
        constants={},
        fields={"suggestion": state_field(T.optional(T.text()), None)},
        commands={
            "suggest": Command(
                inputs={"activity": T.text()},
                effects=(set_once("suggestion", input_("activity")),),
            )
        },
        view={"suggestion": field("suggestion")},
    )
    state_map = SharedStateMap(
        SharedState(activity=activity_state), state_id="weekend-activity"
    )
    activity = state_map.by("this-weekend").activity

    suggestion = QuestionMultipleChoice(
        question_name="suggestion",
        question_text="What activity should we do this weekend?",
        question_options=["Sailing", "Biking", "Hiking", "Beach"],
    )
    approval = QuestionYesNo(
        question_name="approved",
        question_text=(
            "John suggested {{ shared_state.activity.suggestion }} for this "
            "weekend. Do you approve?"
        ),
    )

    workflow = HumanWorkflow(
        "weekend-activity-approval",
        [
            HumanStep(
                "suggest-activity",
                Survey([suggestion]),
                ParticipantSelector.role("proposer"),
                writes=(activity.suggest(activity=suggestion.answer),),
            ),
            HumanStep(
                "approve-activity",
                Survey([approval]),
                ParticipantSelector.role("approver"),
                after=("suggest-activity",),
                reads=(activity.read(),),
            ),
        ],
    )
    return workflow, state_map


def participants():
    return [
        Agent(
            name=PROPOSER_EMAIL,
            traits={"role": "proposer", "email": PROPOSER_EMAIL},
        ),
        Agent(
            name=APPROVER_EMAIL,
            traits={"role": "approver", "email": APPROVER_EMAIL},
        ),
    ]


class DemoAnswerer:
    """Deterministic stand-in for clicks in the two emailed surveys."""

    def answer(self, agent, opened):
        if opened.step_name == "suggest-activity":
            return {"suggestion": "Sailing"}
        assert "Sailing" in opened.survey.questions[0].question_text
        return {"approved": "Yes"}


def run_demo(root: Path):
    workflow, state_map = build_workflow()
    store = SQLiteWorkflowStore(root / "workflow.sqlite")
    state_backend = SQLiteStateBackend(state_map, root / "state.sqlite")
    coordinator = WorkflowCoordinator(
        workflow,
        store,
        state_backends={state_map.state_id: state_backend},
    )
    people = participants()
    instance_id = coordinator.launch(people)
    simulation = WorkflowSimulation(
        coordinator,
        {person.name: person for person in people},
        DemoAnswerer(),
    )
    simulation.run(instance_id)
    return store.events(instance_id), simulation.inbox.messages


def run_live(root: Path, *, poll_interval: float = 10.0):
    """Send real Humanize emails and coordinate responses until completion."""
    root.mkdir(parents=True, exist_ok=True)
    workflow, state_map = build_workflow()
    store = SQLiteWorkflowStore(root / "workflow.sqlite")
    state_backend = SQLiteStateBackend(state_map, root / "state.sqlite")
    coordinator = WorkflowCoordinator(
        workflow,
        store,
        state_backends={state_map.state_id: state_backend},
    )
    instances = store.rows(
        "SELECT id, status FROM workflow_instances ORDER BY created_at LIMIT 1"
    )
    instance_id = (
        instances[0]["id"] if instances else coordinator.launch(participants())
    )
    adapter = HumanizeDeliveryAdapter(coordinator)
    dispatcher = OutboxDispatcher(store, adapter)

    while True:
        receipts = dispatcher.dispatch()
        for receipt in receipts:
            print(f"Humanize survey sent: {receipt.external_id}", flush=True)
        imported = adapter.poll_completed()
        if imported:
            print(f"Imported {imported} completed response(s).", flush=True)
        status = store.rows(
            "SELECT status FROM workflow_instances WHERE id = ?", (instance_id,)
        )[0]["status"]
        if status == "completed":
            print("Weekend activity workflow completed.", flush=True)
            return instance_id
        time.sleep(poll_interval)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--live", action="store_true", help="Send real Humanize email")
    parser.add_argument(
        "--root", type=Path, default=Path("/tmp/edsl-weekend-activity-workflow")
    )
    parser.add_argument("--poll-interval", type=float, default=10.0)
    args = parser.parse_args()
    if args.live:
        run_live(args.root, poll_interval=args.poll_interval)
    else:
        with TemporaryDirectory() as directory:
            events, messages = run_demo(Path(directory))
            print("Delivery order:")
            for message in messages:
                print(f"  {message.participant_id}: {message.work_item_id}")
            print("Events:")
            for event in events:
                print(f"  {event['sequence']}: {event['kind']}")

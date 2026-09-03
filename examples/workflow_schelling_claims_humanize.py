"""Run Schelling's tacit-claims game through real Humanize email delivery.

Initial delivery:
    uv run python examples/workflow_schelling_claims_humanize.py --send-once

Import responses and send newly released payoff notices:
    uv run python examples/workflow_schelling_claims_humanize.py --poll-once
"""

from __future__ import annotations

import argparse
from pathlib import Path

from edsl import Agent, QuestionFreeText, QuestionNumerical, Survey
from edsl.workflows import (
    HumanizeDeliveryAdapter,
    HumanWorkflow,
    OutboxDispatcher,
    SQLiteWorkflowStore,
    Workflow,
    WorkflowCoordinator,
    choose,
    role,
)


PLAYER_EMAILS = (
    "john.joseph.horton+p1@gmail.com",
    "john.joseph.horton+p2@gmail.com",
)
DEFAULT_ROOT = Path("examples/workflow_human_runs/schelling-claims-p1-p2")


def build_workflow() -> HumanWorkflow:
    builder = Workflow(
        "Schelling tacit claims by email",
        metadata={"prize": 100, "source": "Kagel and Roth handbook, p. 12"},
    )
    claim_q = QuestionNumerical(
        question_name="claim",
        question_text=(
            "You and one other participant are dividing a 100-token prize without "
            "communicating. Privately claim an integer from 0 to 100. If your two "
            "claims total at most 100, each person receives exactly their claim. "
            "If they total more than 100, both receive zero."
        ),
        min_value=0,
        max_value=100,
        include_comment=False,
    )
    claims = builder.step(
        "claim",
        Survey([claim_q]),
        assigned_to=role("player"),
        visible_to=role("workflow-system"),
        metadata={"performed_by": "human", "channel": "humanize-email"},
    )
    total = claims.outputs("claim").sum()
    feasible = total.compare_at_most(100)
    own = claims.submissions.each("claim")
    outcome = builder.derive(
        "outcome",
        total=total,
        feasible=feasible,
        payoffs=own.map(choose(feasible, own.value, 0)),
    )
    notice_q = QuestionFreeText(
        question_name="acknowledgement",
        question_text=(
            f"The two claims totaled {outcome.field('total').template}. "
            f"Feasible allocation: {outcome.field('feasible').template}. "
            f"Your authoritative payoff is "
            f"{outcome.field('payoffs').for_participant()} tokens. "
            "Please acknowledge receipt."
        ),
    )
    builder.step(
        "payoff-notice",
        Survey([notice_q]),
        assigned_to=role("player"),
        after=claims,
        metadata={"performed_by": "human", "channel": "humanize-email"},
    )
    return builder.compile()


def participants() -> tuple[Agent, ...]:
    return tuple(
        Agent(name=email, traits={"role": "player", "email": email})
        for email in PLAYER_EMAILS
    )


def coordinator(root: Path) -> tuple[WorkflowCoordinator, str]:
    root.mkdir(parents=True, exist_ok=True)
    store = SQLiteWorkflowStore(root / "workflow.sqlite")
    workflow = build_workflow()
    existing = store.rows(
        "SELECT id FROM workflow_instances ORDER BY created_at LIMIT 1"
    )
    engine = WorkflowCoordinator(workflow, store)
    instance_id = existing[0]["id"] if existing else engine.launch(participants())
    return engine, instance_id


def advance(root: Path, *, poll: bool) -> dict:
    engine, instance_id = coordinator(root)
    adapter = HumanizeDeliveryAdapter(
        engine, subject_prefix="Schelling tacit claims"
    )
    imported = adapter.poll_completed() if poll else 0
    receipts = OutboxDispatcher(engine.store, adapter).dispatch()
    status = engine.store.rows(
        "SELECT status FROM workflow_instances WHERE id = ?", (instance_id,)
    )[0]["status"]
    return {
        "instance_id": instance_id,
        "imported_responses": imported,
        "sent_human_surveys": [receipt.external_id for receipt in receipts],
        "status": status,
        "root": str(root.resolve()),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--send-once", action="store_true")
    mode.add_argument("--poll-once", action="store_true")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    print(advance(args.root, poll=args.poll_once))

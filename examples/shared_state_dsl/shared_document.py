"""Whole-document revisions with a serializable revision history."""

from edsl.sharedstate import Command, Machine, StateType, append, constant, field, arg, record, reduce, assign, state_field

SPEC = Machine(
    name="SharedDocument",
    constants={
        "title": "Climate cooperation translation chain",
        "initial_text": (
            "The atmosphere does not recognize national borders. Each country "
            "benefits when others reduce emissions, yet each also faces a temptation "
            "to delay its own costly action. Durable cooperation therefore requires "
            "credible commitments, transparent measurement, and a fair distribution "
            "of costs. Wealthier societies have greater capacity to finance the "
            "transition, while poorer societies often face the gravest immediate "
            "risks. A successful agreement must align individual incentives with the "
            "shared interest in a stable climate."
        ),
    },
    fields={
        "text": state_field(StateType.text(), constant("initial_text")),
        "revisions": state_field(StateType.sequence(StateType.map()), []),
    },
    commands={
        "revise": Command(
            inputs={"author": StateType.text(), "round": StateType.integer(minimum=1), "text": StateType.text(), "rationale": StateType.text()},
            effects=(
                assign("text", arg("text")),
                append("revisions", record(author=arg("author"), round=arg("round"), rationale=arg("rationale"), changed=arg("text") != field("text"))),
            ),
        )
    },
    view={
        "title": constant("title"),
        "text": field("text"),
        "revision_count": field("revisions").length(),
        "recent_revisions": reduce("tail", field("revisions"), count=10),
    },
)

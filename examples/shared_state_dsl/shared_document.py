"""Whole-document revisions with a serializable revision history."""

from edsl.sharedstate import Command, Machine, T, append, constant, field, input_, record, reduce_, set_, state_field

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
        "text": state_field(T.text(), constant("initial_text")),
        "revisions": state_field(T.sequence(T.map()), []),
    },
    commands={
        "revise": Command(
            inputs={"author": T.text(), "round": T.integer(minimum=1), "text": T.text(), "rationale": T.text()},
            effects=(
                set_("text", input_("text")),
                append("revisions", record(author=input_("author"), round=input_("round"), rationale=input_("rationale"), changed=input_("text") != field("text"))),
            ),
        )
    },
    view={
        "title": constant("title"),
        "text": field("text"),
        "revision_count": field("revisions").length(),
        "recent_revisions": reduce_("tail", field("revisions"), count=10),
    },
)

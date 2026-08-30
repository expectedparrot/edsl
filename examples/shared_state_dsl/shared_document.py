"""Whole-document revisions with a serializable revision history."""

from edsl.sharedstate import Command, Machine, T, append, constant, field, input_, record, reduce_, set_, state_field

SPEC = Machine(
    name="SharedDocument",
    constants={"title": "Activity plan", "initial_text": "We need to choose an activity."},
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

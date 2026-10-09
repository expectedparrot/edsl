"""An append-only sequence of typed records."""

from edsl.sharedstate import Command, Machine, StateType, append, field, arg, reduce_, state_field

SPEC = Machine(
    name="SharedLog",
    constants={},
    fields={"entries": state_field(StateType.sequence(), [])},
    commands={
        "append": Command(
            inputs={"entry": StateType.any()},
            effects=(append("entries", arg("entry")),),
        )
    },
    view={
        "entries": field("entries"),
        "count": field("entries").length(),
        "tail": reduce_("tail", field("entries"), count=10),
    },
)

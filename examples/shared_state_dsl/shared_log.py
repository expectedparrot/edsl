"""An append-only sequence of typed records."""

from edsl.sharedstate import Command, Machine, T, append, field, input_, reduce_, state_field

SPEC = Machine(
    name="SharedLog",
    constants={},
    fields={"entries": state_field(T.sequence(), [])},
    commands={
        "append": Command(
            inputs={"entry": T.any()},
            effects=(append("entries", input_("entry")),),
        )
    },
    view={
        "entries": field("entries"),
        "count": field("entries").length(),
        "tail": reduce_("tail", field("entries"), count=10),
    },
)

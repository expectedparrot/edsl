"""A typed dictionary with optional first-write-wins semantics."""

from edsl.sharedstate import Command, Machine, T, field, input_, put, state_field

SPEC = Machine(
    name="SharedRegister",
    constants={"value_type": T.any(), "write_once": True},
    fields={"values": state_field(T.map(T.text(), T.any()), {})},
    commands={
        "set": Command(
            inputs={"key": T.text(), "value": T.any()},
            effects=(put("values", input_("key"), input_("value"), once=True),),
        )
    },
    view={"values": field("values")},
)

"""A typed dictionary with optional first-write-wins semantics."""

from edsl.sharedstate import Command, Machine, StateType, field, arg, put, state_field

SPEC = Machine(
    name="SharedRegister",
    constants={"value_type": StateType.any(), "write_once": True},
    fields={"values": state_field(StateType.map(StateType.text(), StateType.any()), {})},
    commands={
        "set": Command(
            inputs={"key": StateType.text(), "value": StateType.any()},
            effects=(put("values", arg("key"), arg("value"), once=True),),
        )
    },
    view={"values": field("values")},
)

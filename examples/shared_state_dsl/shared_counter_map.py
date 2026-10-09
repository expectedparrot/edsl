"""Configured counters updated from a sequence of selected keys."""

from edsl.sharedstate import Command, Machine, StateType, field, arg, reduce_, set_, state_field

KEYS = ("bike ride", "sailing", "hike", "beach day")
SPEC = Machine(
    name="SharedCounterMap",
    constants={"keys": KEYS},
    fields={"counts": state_field(StateType.map(StateType.text(), StateType.integer(minimum=0)), {key: 0 for key in KEYS})},
    commands={
        "tally": Command(
            inputs={"values": StateType.sequence(StateType.choice(KEYS))},
            effects=(set_("counts", reduce_("increment_keys", field("counts"), keys=arg("values"))),),
        )
    },
    view={"counts": field("counts")},
)

"""Configured counters updated from a sequence of selected keys."""

from edsl.sharedstate import Command, Machine, T, field, input_, reduce_, set_, state_field

KEYS = ("bike ride", "sailing", "hike", "beach day")
SPEC = Machine(
    name="SharedCounterMap",
    constants={"keys": KEYS},
    fields={"counts": state_field(T.map(T.text(), T.integer(minimum=0)), {key: 0 for key in KEYS})},
    commands={
        "tally": Command(
            inputs={"values": T.sequence(T.choice(KEYS))},
            effects=(set_("counts", reduce_("increment_keys", field("counts"), keys=input_("values"))),),
        )
    },
    view={"counts": field("counts")},
)

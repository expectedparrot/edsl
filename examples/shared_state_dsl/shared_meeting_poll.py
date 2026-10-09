"""A typed poll that records each participant's available meeting times."""

from edsl.sharedstate import Command, Machine, StateType, constant, field, arg, put, reduce, , state_field, when


SLOTS = (
    "Tuesday 10:00 AM",
    "Tuesday 2:00 PM",
    "Wednesday 10:00 AM",
    "Wednesday 2:00 PM",
    "Thursday 10:00 AM",
)

new_participant = ~field("availability").contains(arg("participant"))

SPEC = Machine(
    name="MeetingAvailabilityPoll",
    constants={"slots": SLOTS},
    fields={
        "availability": state_field(
            StateType.map(StateType.text(), StateType.sequence(StateType.choice(SLOTS))), {}
        ),
        "counts": state_field(
            StateType.map(StateType.text(), StateType.integer(minimum=0)), {slot: 0 for slot in SLOTS}
        ),
    },
    commands={
        "respond": Command(
            inputs={
                "participant": StateType.text(),
                "available_slots": StateType.sequence(StateType.choice(SLOTS)),
            },
            effects=(
                when(
                    new_participant,
                    put(
                        "availability",
                        arg("participant"),
                        arg("available_slots"),
                    ),
                ),
                when(
                    new_participant,
                    assign(
                        "counts",
                        reduce(
                            "increment_keys",
                            field("counts"),
                            keys=arg("available_slots"),
                        ),
                    ),
                ),
            ),
        )
    },
    view={
        "slots": constant("slots"),
        "availability": field("availability"),
        "counts": field("counts"),
        "response_count": field("availability").length(),
    },
)

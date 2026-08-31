"""A typed poll that records each participant's available meeting times."""

from edsl.sharedstate import Command, Machine, T, constant, field, input_, put, reduce_, set_, state_field, when


SLOTS = (
    "Tuesday 10:00 AM",
    "Tuesday 2:00 PM",
    "Wednesday 10:00 AM",
    "Wednesday 2:00 PM",
    "Thursday 10:00 AM",
)

new_participant = ~field("availability").contains(input_("participant"))

SPEC = Machine(
    name="MeetingAvailabilityPoll",
    constants={"slots": SLOTS},
    fields={
        "availability": state_field(
            T.map(T.text(), T.sequence(T.choice(SLOTS))), {}
        ),
        "counts": state_field(
            T.map(T.text(), T.integer(minimum=0)), {slot: 0 for slot in SLOTS}
        ),
    },
    commands={
        "respond": Command(
            inputs={
                "participant": T.text(),
                "available_slots": T.sequence(T.choice(SLOTS)),
            },
            effects=(
                when(
                    new_participant,
                    put(
                        "availability",
                        input_("participant"),
                        input_("available_slots"),
                    ),
                ),
                when(
                    new_participant,
                    set_(
                        "counts",
                        reduce_(
                            "increment_keys",
                            field("counts"),
                            keys=input_("available_slots"),
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

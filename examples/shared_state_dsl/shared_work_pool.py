"""Atomic work claiming using general sequence and map expressions."""

from edsl.sharedstate import Command, Machine, T, constant, current, field, input_, put, record, set_, state_field

unclaimed = ~field("claims").contains(input_("claimant"))

SPEC = Machine(
    name="SharedWorkPool",
    constants={"items": ({"id": "W1"}, {"id": "W2"})},
    fields={
        "available": state_field(T.sequence(), constant("items")),
        "claims": state_field(T.map(), {}),
        "completed": state_field(T.map(), {}),
    },
    commands={
        "claim_before": Command(
            inputs={"claimant": T.text()},
            require=unclaimed,
            effects=(
                put("claims", input_("claimant"), field("available").first()),
                set_("available", field("available").drop_first()),
            ),
            timing="before_question",
        ),
        "complete": Command(
            inputs={"claimant": T.text(), "result": T.any()},
            require=field("claims").contains(input_("claimant")),
            effects=(put("completed", input_("claimant"), record(item=field("claims").get(input_("claimant")), result=input_("result"))),),
        ),
    },
    view={
        "available": field("available"),
        "my_claim": field("claims").get(current("name")),
        "claim_count": field("claims").length(),
        "completed": field("completed"),
    },
)

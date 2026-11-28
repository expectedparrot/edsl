"""Atomic work claiming using general sequence and map expressions."""

from edsl.sharedstate import Command, Machine, StateType, constant, current, field, arg, put, record, assign, state_field

unclaimed = ~field("claims").contains(arg("claimant"))

SPEC = Machine(
    name="SharedWorkPool",
    constants={"items": ({"id": "W1"}, {"id": "W2"})},
    fields={
        "available": state_field(StateType.sequence(), constant("items")),
        "claims": state_field(StateType.map(), {}),
        "completed": state_field(StateType.map(), {}),
    },
    commands={
        "claim_before": Command(
            inputs={"claimant": StateType.text()},
            require=unclaimed,
            effects=(
                put("claims", arg("claimant"), field("available").first()),
                assign("available", field("available").drop_first()),
            ),
            timing="before_question",
        ),
        "complete": Command(
            inputs={"claimant": StateType.text(), "result": StateType.any()},
            require=field("claims").contains(arg("claimant")),
            effects=(put("completed", arg("claimant"), record(item=field("claims").get(arg("claimant")), result=arg("result"))),),
        ),
    },
    view={
        "available": field("available"),
        "my_claim": field("claims").get(current("name")),
        "claim_count": field("claims").length(),
        "completed": field("completed"),
    },
)

"""Finite funding expressed with arithmetic and collection expressions."""

from edsl.sharedstate import Command, Machine, StateType, append, constant, expr, field, arg, put, record, assign, state_field

granted = expr("minimum", arg("amount"), field("remaining"))

SPEC = Machine(
    name="SharedBudgetPool",
    constants={"total": 100, "projects": ("park", "library")},
    fields={
        "remaining": state_field(StateType.number(minimum=0), constant("total")),
        "funded": state_field(StateType.map(StateType.text(), StateType.number()), {}),
        "allocations": state_field(StateType.sequence(), []),
    },
    commands={
        "fund": Command(
            inputs={
                "sponsor": StateType.text(),
                "project": StateType.choice(constant("projects")),
                "amount": StateType.number(minimum=0),
            },
            effects=(
                assign("remaining", field("remaining") - granted),
                put("funded", arg("project"), field("funded").get(arg("project"), 0) + granted),
                append("allocations", record(sponsor=arg("sponsor"), project=arg("project"), requested=arg("amount"), granted=granted)),
            ),
        )
    },
    view={"remaining": field("remaining"), "funded": field("funded"), "allocations": field("allocations")},
    complete_when=field("remaining") == 0,
)

"""Finite funding expressed with arithmetic and collection expressions."""

from edsl.sharedstate import Command, Machine, T, append, constant, expr, field, input_, put, record, set_, state_field

granted = expr("minimum", input_("amount"), field("remaining"))

SPEC = Machine(
    name="SharedBudgetPool",
    constants={"total": 100, "projects": ("park", "library")},
    fields={
        "remaining": state_field(T.number(minimum=0), constant("total")),
        "funded": state_field(T.map(T.text(), T.number()), {}),
        "allocations": state_field(T.sequence(), []),
    },
    commands={
        "fund": Command(
            inputs={
                "sponsor": T.text(),
                "project": T.choice(constant("projects")),
                "amount": T.number(minimum=0),
            },
            effects=(
                set_("remaining", field("remaining") - granted),
                put("funded", input_("project"), field("funded").get(input_("project"), 0) + granted),
                append("allocations", record(sponsor=input_("sponsor"), project=input_("project"), requested=input_("amount"), granted=granted)),
            ),
        )
    },
    view={"remaining": field("remaining"), "funded": field("funded"), "allocations": field("allocations")},
    complete_when=field("remaining") == 0,
)

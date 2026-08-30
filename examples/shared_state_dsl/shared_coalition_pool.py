"""Capacity-constrained membership using conditional generic effects."""

from edsl.sharedstate import Command, Machine, T, append, constant, field, input_, put, record, state_field, when

previous = field("memberships").get(input_("member"))
target_members = field("members").get(input_("coalition"), [])
capacity = constant("capacities").get(input_("coalition"))
accepted = (previous == input_("coalition")) | (target_members.length() < capacity)
moving = accepted & (previous != input_("coalition"))
leaving = moving & (previous != None)  # noqa: E711

SPEC = Machine(
    name="SharedCoalitionPool",
    constants={"capacities": {"red": 2, "blue": 2}},
    fields={
        "memberships": state_field(T.map(), {}),
        "members": state_field(T.map(T.text(), T.sequence(T.text())), {"red": [], "blue": []}),
        "requests": state_field(T.sequence(), []),
    },
    commands={
        "request": Command(
            inputs={"member": T.text(), "coalition": T.choice(("red", "blue")), "round": T.number()},
            effects=(
                when(moving, put("memberships", input_("member"), input_("coalition"))),
                when(moving, put("members", input_("coalition"), target_members.appended(input_("member")))),
                when(leaving, put("members", previous, field("members").get(previous, []).removed(input_("member")))),
                append("requests", record(member=input_("member"), coalition=input_("coalition"), round=input_("round"), accepted=accepted)),
            ),
        )
    },
    view={"memberships": field("memberships"), "members": field("members"), "requests": field("requests")},
)

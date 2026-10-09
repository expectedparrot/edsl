"""Capacity-constrained membership using conditional generic effects."""

from edsl.sharedstate import Command, Machine, StateType, append, constant, field, arg, put, record, state_field, when

previous = field("memberships").get(arg("member"))
target_members = field("members").get(arg("coalition"), [])
capacity = constant("capacities").get(arg("coalition"))
accepted = (previous == arg("coalition")) | (target_members.length() < capacity)
moving = accepted & (previous != arg("coalition"))
leaving = moving & (previous != None)  # noqa: E711

SPEC = Machine(
    name="SharedCoalitionPool",
    constants={"capacities": {"red": 2, "blue": 2}},
    fields={
        "memberships": state_field(StateType.map(), {}),
        "members": state_field(StateType.map(StateType.text(), StateType.sequence(StateType.text())), {"red": [], "blue": []}),
        "requests": state_field(StateType.sequence(), []),
    },
    commands={
        "request": Command(
            inputs={"member": StateType.text(), "coalition": StateType.choice(("red", "blue")), "round": StateType.number()},
            effects=(
                when(moving, put("memberships", arg("member"), arg("coalition"))),
                when(moving, put("members", arg("coalition"), target_members.appended(arg("member")))),
                when(leaving, put("members", previous, field("members").get(previous, []).removed(arg("member")))),
                append("requests", record(member=arg("member"), coalition=arg("coalition"), round=arg("round"), accepted=accepted)),
            ),
        )
    },
    view={"memberships": field("memberships"), "members": field("members"), "requests": field("requests")},
)

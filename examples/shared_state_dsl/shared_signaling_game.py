"""Worker signal followed by an employer decision."""

from edsl.sharedstate import Command, Machine, StateType, choose, constant, field, arg, map_of, set_, state_field

cost = field("education") * field("signal_cost")
payoffs = map_of(
    (field("worker"), choose(field("hired"), constant("wage"), 0) - cost),
    (field("employer"), choose(field("hired"), field("productivity") - constant("wage"), 0)),
)
SPEC = Machine(
    name="SharedSignalingGame",
    constants={"wage": 60},
    fields={name: state_field(type_, None) for name, type_ in {
        "worker": StateType.optional(StateType.text()), "employer": StateType.optional(StateType.text()),
        "education": StateType.optional(StateType.number()), "productivity": StateType.optional(StateType.number()),
        "signal_cost": StateType.optional(StateType.number()), "hired": StateType.optional(StateType.boolean()),
    }.items()},
    commands={
        "signal": Command(
            inputs={"worker": StateType.text(), "productivity": StateType.number(), "signal_cost": StateType.number(), "education": StateType.number(minimum=0, maximum=3)},
            effects=(set_("worker", arg("worker")), set_("education", arg("education")), set_("productivity", arg("productivity")), set_("signal_cost", arg("signal_cost"))),
        ),
        "decide": Command(
            inputs={"employer": StateType.text(), "decision": StateType.choice(("hire", "do_not_hire"))},
            require=field("education") != None,  # noqa: E711
            effects=(set_("employer", arg("employer")), set_("hired", arg("decision") == "hire")),
        ),
    },
    view={"worker": field("worker"), "employer": field("employer"), "education": field("education"), "wage": constant("wage"), "hired": field("hired"), "payoffs": choose(field("hired") != None, payoffs, None)},  # noqa: E711
    complete_when=field("hired") != None,  # noqa: E711
)

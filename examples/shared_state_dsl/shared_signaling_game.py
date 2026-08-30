"""Worker signal followed by an employer decision."""

from edsl.sharedstate import Command, Machine, T, choose, constant, field, input_, map_of, set_, state_field

cost = field("education") * field("signal_cost")
payoffs = map_of(
    (field("worker"), choose(field("hired"), constant("wage"), 0) - cost),
    (field("employer"), choose(field("hired"), field("productivity") - constant("wage"), 0)),
)
SPEC = Machine(
    name="SharedSignalingGame",
    constants={"wage": 60},
    fields={name: state_field(type_, None) for name, type_ in {
        "worker": T.optional(T.text()), "employer": T.optional(T.text()),
        "education": T.optional(T.number()), "productivity": T.optional(T.number()),
        "signal_cost": T.optional(T.number()), "hired": T.optional(T.boolean()),
    }.items()},
    commands={
        "signal": Command(
            inputs={"worker": T.text(), "productivity": T.number(), "signal_cost": T.number(), "education": T.number(minimum=0, maximum=3)},
            effects=(set_("worker", input_("worker")), set_("education", input_("education")), set_("productivity", input_("productivity")), set_("signal_cost", input_("signal_cost"))),
        ),
        "decide": Command(
            inputs={"employer": T.text(), "decision": T.choice(("hire", "do_not_hire"))},
            require=field("education") != None,  # noqa: E711
            effects=(set_("employer", input_("employer")), set_("hired", input_("decision") == "hire")),
        ),
    },
    view={"worker": field("worker"), "employer": field("employer"), "education": field("education"), "wage": constant("wage"), "hired": field("hired"), "payoffs": choose(field("hired") != None, payoffs, None)},  # noqa: E711
    complete_when=field("hired") != None,  # noqa: E711
)

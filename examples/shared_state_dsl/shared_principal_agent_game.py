"""Success-bonus contract followed by a private effort choice."""

from edsl.sharedstate import Command, Machine, T, choose, constant, current, field, input_, map_of, set_, state_field

probability = choose(field("effort") == "high", constant("high_probability"), constant("low_probability"))
cost = choose(field("effort") == "high", constant("high_cost"), 0)
expected = map_of(
    (field("principal"), probability * (constant("output_value") - field("bonus"))),
    (field("worker"), probability * field("bonus") - cost),
)
SPEC = Machine(
    name="SharedPrincipalAgentGame",
    constants={"output_value": 100, "high_probability": 0.8, "low_probability": 0.2, "high_cost": 20},
    fields={name: state_field(T.optional(type_), None) for name, type_ in {
        "principal": T.text(), "worker": T.text(), "bonus": T.number(), "effort": T.text(),
    }.items()},
    commands={
        "contract": Command(inputs={"principal": T.text(), "bonus": T.number(minimum=0, maximum=constant("output_value"))}, effects=(set_("principal", input_("principal")), set_("bonus", input_("bonus")))),
        "effort": Command(inputs={"worker": T.text(), "effort": T.choice(("high", "low"))}, require=field("bonus") != None, effects=(set_("worker", input_("worker")), set_("effort", input_("effort")))),  # noqa: E711
    },
    view={
        "principal": field("principal"), "worker": field("worker"), "bonus": field("bonus"),
        "effort_chosen": field("effort") != None,  # noqa: E711
        "effort": choose(field("effort") != None, choose(current("closed"), field("effort"), "private"), None),  # noqa: E711
        "success_probability": choose(field("effort") != None, probability, None),  # noqa: E711
        "expected_payoffs": choose(field("effort") != None, expected, None),  # noqa: E711
    },
    complete_when=field("effort") != None,  # noqa: E711
)
